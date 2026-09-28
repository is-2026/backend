# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any, List
from uuid import UUID
from app.models.comportamiento import Comportamiento
from app.models.crear_comportamiento_input import CrearComportamientoInput
from app.models.error import Error
from app.security_api import get_token_bearerAuth

class BaseComportamientosApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseComportamientosApi.subclasses = BaseComportamientosApi.subclasses + (cls,)
    async def listar_comportamientos(
        self,
    ) -> List[Comportamiento]:
        ...


    async def crear_comportamiento(
        self,
        crear_comportamiento_input: CrearComportamientoInput,
    ) -> Comportamiento:
        ...


    async def obtener_comportamiento(
        self,
        comportamiento_id: UUID,
    ) -> Comportamiento:
        ...


    async def editar_comportamiento(
        self,
        comportamiento_id: UUID,
        crear_comportamiento_input: CrearComportamientoInput,
    ) -> Comportamiento:
        ...


    async def eliminar_comportamiento(
        self,
        comportamiento_id: UUID,
    ) -> None:
        ...
