import uuid
 
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import NamedTuple
 
from app.db.club import ClubDB
from app.db.friendly import FriendlyDB, FriendlyPlayerDB
from app.db.match import MatchDB
 
 
class SquadPlayerData(NamedTuple):
    player_id : uuid.UUID
    is_starter : bool
    behavior_id : uuid.UUID 
 
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
                    hashed_password : str,
                    players: list[SquadPlayerData]
                    )-> FriendlyDB:
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
 
    async def get(self, friendly_id: uuid.UUID) -> FriendlyDB | None:
        return await self._session.get(FriendlyDB, friendly_id)
 
    async def get_club_name(self, club_id: uuid.UUID) -> str | None:
        result = await self._session.execute(
            select(ClubDB.club_name).where(ClubDB.id == club_id)
        )
        return result.scalar_one_or_none()
 
    async def accept(
                    self,
                    friendly_id: uuid.UUID,
                    rival_club_id: uuid.UUID,
                    players: list[SquadPlayerData]
                    ) -> tuple[FriendlyDB, MatchDB]:
        result = await self._session.execute(
            select(FriendlyDB)
            .where(FriendlyDB.id == friendly_id)
            .with_for_update()
            .execution_options(populate_existing=True)  # lee el estado real, no el que ya tenía la sesión
        )
        friendly = result.scalar_one_or_none()
        if friendly is None or friendly.status != "waiting_for_rival":
            await self._session.rollback()
            raise FriendlyUnavailable()
 
        match = MatchDB(
            id=uuid.uuid4(),
            home_club_id=friendly.creator_club_id,
            away_club_id=rival_club_id,
        )
        self._session.add(match)
        await self._session.flush()  # el partido tiene que existir antes de setear friendly.match_id (FK)
 
        friendly.rival_club_id = rival_club_id
        friendly.status = "accepted"
        friendly.match_id = match.id
 
        self._session.add_all([
            FriendlyPlayerDB(
                id=uuid.uuid4(),
                friendly_id=friendly.id,
                club_id=rival_club_id,
                player_id=player.player_id,
                is_starter=player.is_starter,
                behavior_id=player.behavior_id,
            )
            for player in players
        ])
        try:
            await self._session.commit()
        except IntegrityError as exc_info:
            await self._session.rollback()
            raise InvalidSquad() from exc_info
 
        await self._session.refresh(friendly)
        await self._session.refresh(match)
        return friendly, match
 

