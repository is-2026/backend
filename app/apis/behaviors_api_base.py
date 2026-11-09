 # coding: utf-8

from typing import Any, ClassVar, Dict, List, Tuple  # noqa: F401
from uuid import UUID

from app.models.behavior import Behavior
from app.models.create_behavior_input import CreateBehaviorInput, UpdateBehaviorInput
from app.models.error import Error
from app.models.behavior_test_input import BehaviorTestInput, BehaviorTestStarted
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
        update_behavior_input: UpdateBehaviorInput,
        club_id : UUID
    ) -> Behavior:
        ...


    async def delete_behavior(
        self,
        behavior_id: UUID,
        club_id : UUID
    ) -> None:
        ...
    
    
    async def test_behavior(
        self,
        behavior_test_input: BehaviorTestInput,
        club_id: UUID,
    ) -> BehaviorTestStarted:
        ...