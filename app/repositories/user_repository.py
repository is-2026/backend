import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.user import UserDB


class EmailExists(Exception):
    """Ya existe un usuario con ese email."""


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, email: str, hashed_password: str) -> UserDB:
        user = UserDB(
            id=uuid.uuid4(), email=email, hashed_password=hashed_password
        )
        self._session.add(user)
        try:
            await self._session.commit()
        except IntegrityError as e:
            await self._session.rollback()
            raise EmailExists(email) from e
        return user

    async def get_by_email(self, email: str) -> UserDB | None:
        result = await self._session.execute(
            select(UserDB).where(UserDB.email == email)
        )
        return result.scalar_one_or_none()