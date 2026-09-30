import uuid
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB


class DefaultBehaviorData(NamedTuple):
    name: str
    code: str


class ClubAlreadyExists(Exception):
    """El usuario ya tiene un club"""


class ClubRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        club_name: str,
        avatar_url: str,
        behaviors: list[DefaultBehaviorData],
    ) -> ClubDB:
        club = ClubDB(
            id=uuid.uuid4(), club_name=club_name, avatar_url=avatar_url, user_id=user_id
        )
        self._session.add(club)
        try:
            await self._session.flush()
        except IntegrityError as e:
            await self._session.rollback()
            raise ClubAlreadyExists(user_id) from e

        behaviors_list = [
            BehaviorDB(
                id=uuid.uuid4(),
                name=behavior.name,
                code=behavior.code,
                club_id=club.id,
            )
            for behavior in behaviors
        ]
        self._session.add_all(behaviors_list)
        await self._session.commit()

        await self._session.refresh(club)
        return club

    async def get_by_user_id(self, user_id: uuid.UUID) -> ClubDB | None:
        result = await self._session.execute(
            select(ClubDB).where(ClubDB.user_id == user_id)
        )
        return result.scalar_one_or_none()
