import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import NamedTuple

from app.db.friendly import FriendlyDB, FriendlyPlayerDB


class SquadPlayerData(NamedTuple):
    player_id : uuid.UUID
    is_starter : bool
    behavior_id : uuid.UUID | None

class InvalidSquad(Exception):
    """La convocatoria no es valida (jugadores repetidos/inexistentes)"""

class FriendlyRepository:
    def __init__(self, session : AsyncSession) -> None:
        self._session = session

    def is_private(self, friendly: FriendlyDB) -> bool:
        # true si hay una contraseña guardada, false si es None
        return bool(friendly.hashed_password)

    async def list_available_friendlies(self) -> list[FriendlyDB]:
        consult = select(FriendlyDB).where(FriendlyDB.status == "waiting_for_rival")
        result = await self._session.execute(consult)
        return list(result.scalars().all())
    
    
    async def create(
                    self,
                    creator_club_id: uuid.UUID,
                    hashed_password : str | None,
                    players: list[SquadPlayerData])-> FriendlyDB:
        friendly = FriendlyDB(
            id=uuid.uuid4(),
            creator_club_id= creator_club_id,
            hashed_password = hashed_password,
        )
        self._session.add(friendly)
        await self._session.flush() #hago flush para q exista el friendly.id antes de crear jugadores
        

        players_list=[
            FriendlyPlayerDB(
                id = uuid.uuid4(),
                friendly_id= friendly.id,
                club_id= creator_club_id,
                player_id= player.player_id,
                is_starter= player.is_starter,
                behavior_id= player.behavior_id  
            )
            for player in players
        ]
        self._session.add_all(players_list)
        try:
            await self._session.commit()
        except IntegrityError as exc_info:
            await self._session.rollback()
            raise InvalidSquad() from exc_info

        await self._session.refresh(friendly)
        return friendly  
