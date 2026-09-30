# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import Any, List
from uuid import UUID
from app.models.create_player_input import CreatePlayerInput
from app.models.error import Error
from app.models.player import Player
from app.security_api import get_token_bearerAuth

class BasePlayersApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BasePlayersApi.subclasses = BasePlayersApi.subclasses + (cls,)
    async def list_my_players(
        self,
    ) -> List[Player]:
        ...


    async def create_player(
        self,
        create_player_input: CreatePlayerInput,
        club_id : UUID
    ) -> Player:
        """Crea un nuevo jugador en el club del usuario. Notar que la suma de sus PACSS debe ser exactamente 300."""
        ...


    async def get_my_player(
        self,
        player_id: UUID,
    ) -> Player:
        ...


    async def delete_player(
        self,
        player_id: UUID,
    ) -> None:
        ...
