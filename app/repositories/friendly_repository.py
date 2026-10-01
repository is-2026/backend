import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.friendly import FriendlyDB, FriendlyPlayerDB

from typing import NamedTuple

class SquadPlayerData(NamedTuple):
    player_id : uuid.UUID
    is_starter : bool
    behavior_id : uuid.UUID | None

class InvalidSquad(Exception):
    """Se detectaron jugadores repetidos"""

class FriendlyRepository:
    def __init__(self, session : AsyncSession) -> None:
        self._session = session

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
