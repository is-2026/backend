# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from app.models.auth_login_input import AuthLoginInput
from app.models.auth_response import AuthResponse
from app.models.error import Error
from app.models.usuario_registro_input import UsuarioRegistroInput
from app.security_api import get_token_bearerAuth

class BaseAutenticacionApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseAutenticacionApi.subclasses = BaseAutenticacionApi.subclasses + (cls,)
    async def registrar_usuario(
        self,
        usuario_registro_input: UsuarioRegistroInput,
    ) -> AuthResponse:
        """Crea la cuenta de usuario. El club se crea en un paso separado (POST /club) inmediatamente después, dentro del mismo flujo de onboarding del cliente."""
        ...


    async def iniciar_sesion(
        self,
        auth_login_input: AuthLoginInput,
    ) -> AuthResponse:
        ...


    async def cerrar_sesion(
        self,
    ) -> None:
        ...
