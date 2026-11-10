# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from app.models.change_password_input import ChangePasswordInput
from uuid import UUID
from app.models.user import User
from app.models.error import Error
from app.security_api import get_token_bearerAuth

class BaseUserApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseUserApi.subclasses = BaseUserApi.subclasses + (cls,)
    async def change_password(
        self,
        change_password_input: ChangePasswordInput,
    ) -> None:
        ...
    async def get_my_user(
        self,
        user_id: UUID,
    ) -> User:
        ...
