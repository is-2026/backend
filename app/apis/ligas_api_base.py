# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from pydantic import field_validator
from typing import Any, List, Optional
from uuid import UUID
from app.models.crear_inscripcion_input import CrearInscripcionInput
from app.models.crear_liga_input import CrearLigaInput
from app.models.error import Error
from app.models.liga_detalle import LigaDetalle
from app.models.liga_resumen import LigaResumen
from app.models.partido import Partido
from app.models.tabla_posiciones_item import TablaPosicionesItem
from app.security_api import get_token_bearerAuth

class BaseLigasApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseLigasApi.subclasses = BaseLigasApi.subclasses + (cls,)
    async def listar_ligas(
        self,
    ) -> List[LigaDetalle]:
        """Devuelve tanto ligas públicas como privadas. Solo no iniciadas"""
        ...


    async def crear_liga(
        self,
        crear_liga_input: CrearLigaInput,
    ) -> LigaDetalle:
        """Notar que la cantidad de clubes tiene un mínimo duro de 3. Si se envía password, la liga se considera privada."""
        ...


    async def listar_mis_ligas(
        self,
    ) -> List[LigaResumen]:
        """Identifica al club mediante el token de sesión. Devuelve las ligas en las que el club está inscripto."""
        ...


    async def obtener_liga(
        self,
        liga_id: UUID,
    ) -> LigaDetalle:
        ...


    async def cancelar_liga(
        self,
        liga_id: UUID,
    ) -> None:
        """Solo el creador puede cancelarla, y solo si no está iniciada."""
        ...


    async def unirse_liga(
        self,
        liga_id: UUID,
        crear_inscripcion_input: CrearInscripcionInput,
    ) -> None:
        """Reserva un cupo para la liga. Se definen 6 jugadores convocados para toda la liga (3 marcados como titulares por defecto, 3 como suplentes). Los titulares enviados se usan como fallback si el club no define la alineación antes de alguno de sus partidos."""
        ...


    async def abandonar_liga(
        self,
        liga_id: UUID,
    ) -> None:
        ...


    async def iniciar_liga(
        self,
        liga_id: UUID,
    ) -> LigaDetalle:
        """Solo el creador puede iniciarla. Cambia el estado a \&quot;iniciada\&quot; y genera el fixture."""
        ...


    async def listar_partidos_liga(
        self,
        liga_id: UUID,
        estado: Optional[str],
    ) -> List[Partido]:
        ...


    async def obtener_tabla(
        self,
        liga_id: UUID,
    ) -> List[TablaPosicionesItem]:
        ...
