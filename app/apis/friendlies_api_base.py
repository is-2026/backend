# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any, List
from uuid import UUID
from app.models.create_friendly_input import CreateFriendlyInput
from app.models.error import Error
from app.models.friendly import Friendly
from app.models.join_friendly_input import JoinFriendlyInput
from app.security_api import get_token_bearerAuth

class BaseFriendliesApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseFriendliesApi.subclasses = BaseFriendliesApi.subclasses + (cls,)
    async def list_friendlies(
        self,
    ) -> List[Friendly]:
        """Devuelve una lista de amistosos que están esperando rival, incluyendo públicos y privados."""
        ...


    async def create_friendly(
        self,
        create_friendly_input: CreateFriendlyInput,
    ) -> Friendly:
        """Crea un amistoso esperando por un rival. Si se envía password, el amistoso se marca como privado."""
        ...


    async def join_friendly(
        self,
        friendly_id: UUID,
        join_friendly_input: JoinFriendlyInput,
    ) -> Friendly:
        """Se une a un amistoso creado por otro club. Si es privado, requiere la contraseña. Al unirse exitosamente, se genera el partido."""
        ...


    async def cancel_friendly(
        self,
        friendly_id: UUID,
    ) -> None:
        """Solo el club creador puede cancelarlo, y solo si aún no se ha unido ningún rival."""
        ...
