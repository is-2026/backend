import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.user_api_base import BaseUserApi
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserApiImpl(BaseUserApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_my_user(self, user_id: uuid.UUID) -> User:
        user = await UserRepository(self._session).get_by_id(user_id)
        if user is None:
            # el token es valido pero el usuario ya no existe
            raise HTTPException(status_code=404, detail="El usuario no existe")
        return User(id=user.id, email=user.email)