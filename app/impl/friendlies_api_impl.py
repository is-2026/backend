import uuid
from fastapi import HTTPException

from app.apis.friendlies_api_base import BaseFriendliesApi
from app.models.friendly import Friendly
from app.repositories.player_repository import PlayerRepository
from app.repositories.friendly_repository import FriendlyRepository, InvalidSquad, SquadPlayerData
from app.models.squad_player_input import SquadPlayerInput
from app.models.create_friendly_input import CreateFriendlyInput
from app.models.join_friendly_input import JoinFriendlyInput
from sqlalchemy.ext.asyncio import AsyncSession
from app.security.passwords import hash_password

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
    async def list_friendlies(self) -> list[Friendly]:
        raise NotImplementedError
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        
        return Friendly(
            id= friendly.id,
            creator_club_id= friendly.creator_club_id,
            rival_club_id = None,
            is_private= hashed_passw is not None,
            status= friendly.status,
            match_id=None
        )

    
    async def join_friendly(
        self, friendly_id: uuid.UUID, join_friendly_input: JoinFriendlyInput
    ) -> Friendly:
        raise NotImplementedError

    async def cancel_friendly(self, friendly_id: uuid.UUID) -> None:
        raise NotImplementedError
                    