# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import Field, field_validator
from typing import Any, List, Optional
from typing_extensions import Annotated
from uuid import UUID
from app.models.busqueda import Busqueda
from app.models.crear_busqueda_input import CrearBusquedaInput
from app.models.crear_desafio_input import CrearDesafioInput
from app.models.desafio import Desafio
from app.models.desafio_respuesta_input import DesafioRespuestaInput
from app.models.error import Error
from app.security_api import get_token_bearerAuth

class BaseAmistososApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseAmistososApi.subclasses = BaseAmistososApi.subclasses + (cls,)
    async def listar_desafios(
        self,
        direccion: Annotated[Optional[str], Field(description="Filtra por desafíos enviados o recibidos por el club")],
    ) -> List[Desafio]:
        ...


    async def enviar_desafio(
        self,
        crear_desafio_input: CrearDesafioInput,
    ) -> Desafio:
        """Incluye el pool de 6 convocados del club retador."""
        ...


    async def cancelar_desafio(
        self,
        desafio_id: UUID,
    ) -> None:
        """Solo el club retador puede cancelarlo, y solo si sigue pendiente."""
        ...


    async def responder_desafio(
        self,
        desafio_id: UUID,
        desafio_respuesta_input: DesafioRespuestaInput,
    ) -> Desafio:
        """Si se acepta, se debe incluir el pool de 6 convocados del club desafiado, y se crea el partido."""
        ...


    async def iniciar_matchmaking(
        self,
        crear_busqueda_input: CrearBusquedaInput,
    ) -> Busqueda:
        """Devuelve el ticket nomás. La notificación de emparejamiento exitoso se recibe de forma asíncrona vía WebSocket en el canal &#x60;/ws/amistosos/busqueda&#x60; (ver especificación AsyncAPI, mensaje &#39;PartidoEncontrado&#39;)."""
        ...


    async def cancelar_matchmaking(
        self,
    ) -> None:
        ...
