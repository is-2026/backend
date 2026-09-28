# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from app.models.cambiar_password_input import CambiarPasswordInput
from app.models.error import Error
from app.security_api import get_token_bearerAuth

class BaseUsuarioApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseUsuarioApi.subclasses = BaseUsuarioApi.subclasses + (cls,)
    async def cambiar_password(
        self,
        cambiar_password_input: CambiarPasswordInput,
    ) -> None:
        ...
