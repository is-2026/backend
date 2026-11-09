# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import List
from uuid import UUID
from app.models.change_avatar_input import ChangeAvatarInput
from app.models.change_default_formation_input import ChangeDefaultFormationInput
from app.models.club import Club
from app.models.create_club_input import CreateClubInput
from app.models.error import Error
from app.models.history_item import HistoryItem
from app.models.change_coach_input import ChangeCoachInput
from app.security_api import get_token_bearerAuth

class BaseClubApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseClubApi.subclasses = BaseClubApi.subclasses + (cls,)
    async def get_my_club(
        self,
        club_id: UUID,
    ) -> Club:
        """Identifica al club mediante el token de sesión."""
        ...


    async def create_club(
        self,
        create_club_input: CreateClubInput,
    ) -> Club:
        ...


    async def change_avatar(
        self,
        change_avatar_input: ChangeAvatarInput,
    ) -> Club:
        ...


    async def change_default_formation(
        self,
        change_default_formation_input: ChangeDefaultFormationInput,
    ) -> Club:
        ...


    async def get_my_history(
        self,
    ) -> List[HistoryItem]:
        ...


    async def get_shared_history(
        self,
        club_id: UUID,
    ) -> List[HistoryItem]:
        """Historial de partidos jugados entre el club del usuario autenticado y el club indicado."""
        ...


    async def get_club(
        self,
        club_id: UUID,
    ) -> Club:
        ...

    async def change_coach(
        self,
        change_coach_input: ChangeCoachInput,
        club_id : UUID
    ) -> Club:
        ...