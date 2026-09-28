# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any, List
from uuid import UUID
from app.models.amistoso import Amistoso
from app.models.crear_amistoso_input import CrearAmistosoInput
from app.models.error import Error
from app.models.unirse_amistoso_input import UnirseAmistosoInput
from app.security_api import get_token_bearerAuth

class BaseAmistososApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseAmistososApi.subclasses = BaseAmistososApi.subclasses + (cls,)
    async def listar_amistosos(
        self,
    ) -> List[Amistoso]:
        """Devuelve una lista de amistosos que están esperando rival, incluyendo públicos y privados."""
        ...


    async def crear_amistoso(
        self,
        crear_amistoso_input: CrearAmistosoInput,
    ) -> Amistoso:
        """Crea un amistoso esperando por un rival. Si se envía password, el amistoso se marca como privado."""
        ...


    async def unirse_amistoso(
        self,
        amistoso_id: UUID,
        unirse_amistoso_input: UnirseAmistosoInput,
    ) -> Amistoso:
        """Se une a un amistoso creado por otro club. Si es privado, requiere la contraseña. Al unirse exitosamente, se genera el partido."""
        ...


    async def cancelar_amistoso(
        self,
        amistoso_id: UUID,
    ) -> None:
        """Solo el club creador puede cancelarlo, y solo si aún no se ha unido ningún rival."""
        ...
