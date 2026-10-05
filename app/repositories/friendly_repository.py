import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import NamedTuple

from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.behavior import BehaviorDB
from app.db.player import PlayerDB

class SquadPlayerData(NamedTuple):
    player_id : uuid.UUID
    is_starter : bool
    behavior_id : uuid.UUID | None

class StarterData(NamedTuple):
    club_id: uuid.UUID
    player: PlayerDB
    code: str

class InvalidSquad(Exception):
    """La convocatoria no es valida (jugadores repetidos/inexistentes)"""

class FriendlyUnavailable(Exception):
    """El amistoso ya tiene rival o fue cancelado"""

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

    async def get_starters_by_match(self, match_id: uuid.UUID) -> list[StarterData]:
        """Titulares de los dos clubes del amistoso de ese partido, con el codigo de su comportamiento."""
        result = await self._session.execute(
            select(FriendlyPlayerDB.club_id, PlayerDB, BehaviorDB.code)
            .join(FriendlyDB, FriendlyDB.id == FriendlyPlayerDB.friendly_id)
            .join(PlayerDB, PlayerDB.id == FriendlyPlayerDB.player_id)
            .join(BehaviorDB, BehaviorDB.id == FriendlyPlayerDB.behavior_id)
            .where(
                FriendlyDB.match_id == match_id,
                FriendlyPlayerDB.is_starter.is_(True),
            )
            .order_by(PlayerDB.number)
        )
        return [StarterData(*row) for row in result.all()]