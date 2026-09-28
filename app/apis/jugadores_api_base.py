# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any, List
from uuid import UUID
from app.models.crear_jugador_input import CrearJugadorInput
from app.models.error import Error
from app.models.jugador import Jugador
from app.security_api import get_token_bearerAuth

class BaseJugadoresApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseJugadoresApi.subclasses = BaseJugadoresApi.subclasses + (cls,)
    async def listar_mis_jugadores(
        self,
    ) -> List[Jugador]:
        ...


    async def crear_jugador(
        self,
        crear_jugador_input: CrearJugadorInput,
    ) -> Jugador:
        """Crea un nuevo jugador en el club del usuario. Notar que la suma de sus PACSS debe ser exactamente 300."""
        ...


    async def obtener_mi_jugador(
        self,
        jugador_id: UUID,
    ) -> Jugador:
        ...


    async def eliminar_jugador(
        self,
        jugador_id: UUID,
    ) -> None:
        ...
