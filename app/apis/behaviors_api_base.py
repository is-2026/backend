 # coding: utf-8

from typing import Any, ClassVar, Dict, List, Tuple  # noqa: F401
from uuid import UUID

from app.models.behavior import Behavior
from app.models.create_behavior_input import CreateBehaviorInput
from app.models.error import Error
from app.security_api import get_token_bearerAuth


class BaseBehaviorsApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseBehaviorsApi.subclasses = BaseBehaviorsApi.subclasses + (cls,)
    async def list_behaviors(
        self,
        club_id: UUID
    ) -> List[Behavior]:
        ...


    async def create_behavior(
        self,
        create_behavior_input: CreateBehaviorInput,
        club_id : UUID
    ) -> Behavior:
        ...


    async def get_behavior(
        self,
        behavior_id: UUID,
        club_id: UUID
    ) -> Behavior:
        ...


    async def update_behavior(
        self,
        behavior_id: UUID,
        create_behavior_input: CreateBehaviorInput,
    ) -> Behavior:
        ...


    async def delete_behavior(
        self,
        behavior_id: UUID,
    ) -> None:
        ...
