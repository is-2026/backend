import uuid
import asyncio
import logging
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone

from app.apis.friendlies_api_base import BaseFriendliesApi
from app.models.friendly import Friendly
from app.repositories.player_repository import PlayerRepository
from app.repositories.friendly_repository import FriendlyRepository, InvalidSquad, SquadPlayerData, FriendlyUnavailable
from app.models.squad_player_input import SquadPlayerInput
from app.models.create_friendly_input import CreateFriendlyInput
from app.models.join_friendly_input import JoinFriendlyInput
from sqlalchemy.ext.asyncio import AsyncSession
from app.security.passwords import hash_password, verify_password
from app.ws.connection_manager import ConnectionManager
from app.ws.lobby_friendly import friendly_start_times


INTERNAL_ERROR = 1011
LOBBY_WINDOW_SECONDS = 30
_background_tasks : set[asyncio.Task] = set()  #guarda la referencia a los timers, se agrega al set para que asyncio no lo borre antes


def _validate_squad(players: list[SquadPlayerInput] ) -> None:
    titulares = [t for t in players if t.is_starter]
    if len(titulares) != 3:
        raise HTTPException(status_code=400, detail="Se deben seleccionar exactamente 3 titulares y 3 suplentes")

    ids = [p.player_id for p in players]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Se detectaron jugadores repetidos")

    if any(t.behavior_id is None for t in titulares):
        raise HTTPException(status_code=400, detail="Hay jugadores titulares sin comportamiento asignado")
    
class FriendliesApiImpl(BaseFriendliesApi):
    def __init__(self, session: AsyncSession,
                 lobby_manager: ConnectionManager, #envia los mensajes por ws
                 match_runner= None, #arranca la simulacion
                 window_seconds : float = LOBBY_WINDOW_SECONDS 
                 ) -> None:
        self._session = session
        self._lobby = lobby_manager
        self._match_runner= match_runner
        self._window = window_seconds


    async def list_friendlies(self) -> list[Friendly]:
        repo = FriendlyRepository(self._session)
        friendlies = await repo.list_available_friendlies()
        if not friendlies:
            return []
        names = await repo.get_club_names([f.creator_club_id for f in friendlies])
        return [
            Friendly(
                id=f.id,
                creator_club_id=f.creator_club_id,
                creator_club_name=names.get(f.creator_club_id),
                rival_club_id=f.rival_club_id,
                is_private=repo.is_private(f),
                status=f.status,
                match_id=f.match_id
            )
            for f in friendlies
        ]


    async def create_friendly(self, 
                            create_friendly_input: CreateFriendlyInput,
                            creator_club_id: uuid.UUID) -> Friendly:
        _validate_squad(create_friendly_input.players) #le paso la lista de jugadores

        password = create_friendly_input.password
        hashed_passw = await hash_password(password) if password else None #Chequeo si es publico o privado   

        ids = [p.player_id for p in create_friendly_input.players]
        club_players = await PlayerRepository(self._session).count_club_players( #Verifico que los jugadores existen y son del usuario
            creator_club_id, ids
        )
        if club_players != len(ids):
            raise HTTPException(status_code=400, detail="Se detectaron jugadores que no pertenecen al club")

        data_players =[
            SquadPlayerData(
                player_id= pl.player_id,
                is_starter= pl.is_starter,
                behavior_id= pl.behavior_id
            )
            for pl in create_friendly_input.players
        ]

        try: 
            friendly = await FriendlyRepository(self._session).create(
                creator_club_id=creator_club_id, 
                hashed_password=hashed_passw,
                players= data_players

            )

        except InvalidSquad as exc_info:
            raise HTTPException(status_code=400, 
                                detail="La convocatoria no es valida (jugadores repetidos/inexistentes)"
                                ) from exc_info

        repo = FriendlyRepository(self._session)
        creator_name = await repo.get_club_name(creator_club_id)
        return Friendly(
            id= friendly.id,
            creator_club_id= friendly.creator_club_id,
            creator_club_name= creator_name,
            rival_club_id = None,
            is_private= hashed_passw is not None,
            status= friendly.status,
            match_id=None
        )

    
    async def join_friendly(
                            self, 
                            friendly_id: uuid.UUID, 
                            join_friendly_input: JoinFriendlyInput,
                            club_id : uuid.UUID
                            ) -> Friendly:
        repo = FriendlyRepository(self._session)

        friendly = await repo.get(friendly_id)  #obtengo el id del amistoso
        if friendly is None:  #manejo los errores
            raise HTTPException(status_code=404, detail= "Amistoso no encontrado")
        if friendly.status != "waiting_for_rival":
            raise HTTPException(status_code=409, detail= "El amistoso ya no se encuentra disponible")
        if friendly.creator_club_id == club_id:
            raise HTTPException(status_code=  409, detail= "El club ya se encuentra inscripto en el amistos")
        if friendly.hashed_password is not None:
            passw = join_friendly_input.password
            if not passw or not await verify_password(passw, friendly.hashed_password): #la password se guarda hasheada, así que no se puede comparar texto plano
                raise HTTPException(status_code=400, detail="La contraseña ingresada es incorrecta" )

        _validate_squad(join_friendly_input.players)

        ids = [p.player_id for p in join_friendly_input.players]
        club_players = await PlayerRepository(self._session).count_club_players( #Verifico que los jugadores existen y son del usuario
                    club_id, ids
                )
        if club_players != len(ids):
             raise HTTPException(status_code=400, detail="Se detectaron jugadores que no pertenecen al club")

        data_players =[
            SquadPlayerData(
                player_id= pl.player_id,
                is_starter= pl.is_starter,
                behavior_id= pl.behavior_id
            )
            for pl in join_friendly_input.players
        ]

        try: 
            friendly, match = await repo.accept(friendly_id, club_id, data_players) #repo.accept hace todo en una transaccion
        except FriendlyUnavailable as exc_info:        # por si los 2 usuarios llegan a la vez
            raise HTTPException(status_code=409, 
                                detail="El amistoso ya no se encuentra disponible") from exc_info
        except InvalidSquad as exc_info:
            raise HTTPException(status_code=400, 
                                detail="La convocatoria no es valida (jugadores repetidos/inexistentes)"
                                ) from exc_info
        
        club = await repo.get_club_name(club_id)
        creator_name = await repo.get_club_name(friendly.creator_club_id)
        starts_at = datetime.now(timezone.utc) + timedelta(seconds=self._window)
        friendly_start_times[friendly_id] = starts_at  # para el que entra al lobby después (el rival)
        await self._lobby.broadcast(friendly_id, {#broadcast envia FriendlyClubRegistered a los q esten en el lobby del amistoso
            "type": "friendlyClubRegistered",
            "data": {
                "friendly_id": str(friendly_id),
                "club_id": str(club_id),
                "club_name": club,
                "starts_at": starts_at.isoformat(),
            },
        })
        self._schedule_start(friendly_id, match.id)
        return Friendly(
            id=friendly.id,
            creator_club_id=friendly.creator_club_id,
            creator_club_name=creator_name,
            rival_club_id= club_id,
            is_private= friendly.hashed_password is not None,
            status= friendly.status,
            match_id= match.id
        )

    def _schedule_start(  #Lanza la pantalla de 30s en 2do plano y vuelve para crear el partido, y que no espere 30s el front para la respuesta
                        self, 
                        friendly_id : uuid.UUID, 
                        match_id: uuid.UUID) -> None:
        task = asyncio.create_task(self._start_after_window(friendly_id, match_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard) 

 
    async def _start_after_window(self, #Duerme la ventana, y le manda el match_id con FriendlyStart al front
                                  friendly_id : uuid.UUID,
                                  match_id : uuid.UUID) -> None:
        try:
            await asyncio.sleep(self._window)
            if self._match_runner is not None:
                await self._match_runner.start(match_id) # primero queda en live_matches
            await self._lobby.broadcast(friendly_id, {
                "type": "friendlyStart",
                "data": {"friendly_id": str(friendly_id), "match_id": str(match_id)},
            })
            await self._lobby.close_all(friendly_id) #cierra los ws
        except Exception:
            logging.exception("Falló el inicio del amistoso %s", friendly_id)
            await self._lobby.close_all(friendly_id, code=INTERNAL_ERROR)
        finally:
            friendly_start_times.pop(friendly_id, None)  # la ventana terminó (bien o mal): ya no hay cuenta regresiva

    async def cancel_friendly(self, friendly_id: uuid.UUID) -> None:
        raise NotImplementedError
                    