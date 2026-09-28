# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any
from uuid import UUID
from app.models.cambiar_comportamiento_en_vivo_request import CambiarComportamientoEnVivoRequest
from app.models.enviar_alineacion_input import EnviarAlineacionInput
from app.models.error import Error
from app.models.partido import Partido
from app.models.programar_sustitucion_input import ProgramarSustitucionInput
from app.models.sustitucion import Sustitucion
from app.security_api import get_token_bearerAuth

class BasePartidoApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BasePartidoApi.subclasses = BasePartidoApi.subclasses + (cls,)
    async def obtener_partido(
        self,
        partido_id: UUID,
    ) -> Partido:
        """Devuelve la información actualizada de un partido específico, incluyendo su estado y resultado actual."""
        ...


    async def definir_alineacion(
        self,
        partido_id: UUID,
        enviar_alineacion_input: EnviarAlineacionInput,
    ) -> Partido:
        """Ventana de 30 segundos antes de cada partido (liga y amistoso). Los jugadores incluidos deben pertenecer al pool de convocados de la inscripción (liga) o el desafío/búsqueda (amistoso) correspondiente. Si no se completa a tiempo, el sistema asigna automáticamente los titulares/suplentes por defecto enviados al momento de inscribirse, los 3 comportamientos asignados a los jugadores por defecto, y la formación default del club."""
        ...


    async def cambiar_comportamiento_en_vivo(
        self,
        partido_id: UUID,
        jugador_id: UUID,
        cambiar_comportamiento_en_vivo_request: CambiarComportamientoEnVivoRequest,
    ) -> None:
        """Se aplica desde el siguiente tick del simulador."""
        ...


    async def programar_sustitucion(
        self,
        partido_id: UUID,
        programar_sustitucion_input: ProgramarSustitucionInput,
    ) -> Sustitucion:
        """Se agenda para la próxima ventana disponible (pausa de hidratación o entretiempo). Solo puede haber una sustitución pendiente por club a la vez."""
        ...


    async def desprogramar_sustitucion(
        self,
        partido_id: UUID,
    ) -> None:
        """Cancela la sustitución pendiente del club antes de que se alcance la ventana de cambio."""
        ...
