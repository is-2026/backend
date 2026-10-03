import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.match import MatchDB


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        home_club_id: uuid.UUID,
        away_club_id: uuid.UUID
    ) -> MatchDB:
        # el resto de atributos se asigna por defecto o son none
        match = MatchDB(
            home_club_id=home_club_id,
            away_club_id=away_club_id,
        )
        self._session.add(match)
        await self._session.commit()
        await self._session.refresh(match)
        return match

    async def get_by_id(self, match_id: uuid.UUID) -> MatchDB:
        result = await self._session.execute(
            select(MatchDB).where(MatchDB.id == match_id)
        )
        return result.scalar_one_or_none()


    # TODO: algunos metodos a implementar
        # list_by_league
        # list_history_by_club
        # list_shared_history
