# coding: utf-8

from typing import Any, ClassVar, Dict, List, Tuple  # noqa: F401
from uuid import UUID

from app.models.change_live_behavior_request import ChangeLiveBehaviorRequest
from app.models.error import Error
from app.models.match import Match
from app.models.schedule_substitution_input import ScheduleSubstitutionInput
from app.models.submit_lineup_input import SubmitLineupInput
from app.models.substitution import Substitution
from app.security_api import get_token_bearerAuth


class BaseMatchApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseMatchApi.subclasses = BaseMatchApi.subclasses + (cls,)

    async def get_match(
        self,
        match_id: UUID,
    ) -> Match:
        """Devuelve la información actualizada de un partido específico,
        incluyendo su estado y resultado actual.
        """
        ...

    async def set_lineup(
        self,
        match_id: UUID,
        submit_lineup_input: SubmitLineupInput,
    ) -> Match:
        """Ventana de 30 segundos antes de cada partido (liga y amistoso).
        Los jugadores incluidos deben pertenecer al pool de convocados de la inscripción
        (liga) o el desafío/búsqueda (amistoso) correspondiente. Si no se completa a
        tiempo, el sistema asigna automáticamente los titulares/suplentes por defecto
        enviados al momento de inscribirse, los 3 comportamientos asignados a los
        jugadores por defecto, y la formación default del club.
        """
        ...

    async def change_live_behavior(
        self,
        match_id: UUID,
        player_id: UUID,
        change_live_behavior_request: ChangeLiveBehaviorRequest,
    ) -> None:
        """Se aplica desde el siguiente tick del simulador."""
        ...

    async def schedule_substitution(
        self,
        match_id: UUID,
        schedule_substitution_input: ScheduleSubstitutionInput,
        club_id: UUID,
    ) -> Substitution:
        """Cambia un titular por un suplente con el comportamiento elegido.
        Se ejecuta al terminar la próxima pausa, o la pausa en curso si se pide durante una.
        Solo puede haber una pendiente por club.
        """
        ...

    async def unschedule_substitution(
        self,
        match_id: UUID,
        club_id: UUID,
    ) -> None:
        """Cancela la sustitución pendiente del club antes de que se ejecute."""
        ...
