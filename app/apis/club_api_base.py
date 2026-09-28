# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import List
from uuid import UUID
from app.models.cambiar_avatar_input import CambiarAvatarInput
from app.models.cambiar_formacion_default_input import CambiarFormacionDefaultInput
from app.models.club import Club
from app.models.crear_club_input import CrearClubInput
from app.models.error import Error
from app.models.historial_item import HistorialItem
from app.security_api import get_token_bearerAuth

class BaseClubApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseClubApi.subclasses = BaseClubApi.subclasses + (cls,)
    async def obtener_mi_club(
        self,
    ) -> Club:
        """Identifica al club mediante el token de sesión."""
        ...


    async def crear_club(
        self,
        crear_club_input: CrearClubInput,
    ) -> Club:
        ...


    async def cambiar_avatar(
        self,
        cambiar_avatar_input: CambiarAvatarInput,
    ) -> Club:
        ...


    async def cambiar_formacion_default(
        self,
        cambiar_formacion_default_input: CambiarFormacionDefaultInput,
    ) -> Club:
        ...


    async def obtener_mi_historial(
        self,
    ) -> List[HistorialItem]:
        ...


    async def obtener_historial_compartido(
        self,
        club_id: UUID,
    ) -> List[HistorialItem]:
        """Historial de partidos jugados entre el club del usuario autenticado y el club indicado."""
        ...


    async def obtener_club(
        self,
        club_id: UUID,
    ) -> Club:
        ...
