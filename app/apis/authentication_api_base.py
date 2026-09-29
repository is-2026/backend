# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from app.models.auth_login_input import AuthLoginInput
from app.models.auth_response import AuthResponse
from app.models.error import Error
from app.models.user_register_input import UserRegisterInput
from app.security_api import get_token_bearerAuth

class BaseAuthenticationApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseAuthenticationApi.subclasses = BaseAuthenticationApi.subclasses + (cls,)
    async def register_user(
        self,
        user_register_input: UserRegisterInput,
    ) -> AuthResponse:
        """Crea la cuenta de usuario. El club se crea en un paso separado (POST /club) inmediatamente después, dentro del mismo flujo de onboarding del cliente."""
        ...


    async def login(
        self,
        auth_login_input: AuthLoginInput,
    ) -> AuthResponse:
        ...


    async def logout(
        self,
    ) -> None:
        ...
