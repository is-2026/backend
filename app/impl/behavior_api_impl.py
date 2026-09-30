import uuid
from fastapi import HTTPException

from app.apis.behaviors_api_base import BaseBehaviorsApi
from app.models.behavior import Behavior
from app.repositories.behavior_repository import BehaviorRepository
from sqlalchemy.ext.asyncio import AsyncSession


class BehaviorApiImpl(BaseBehaviorsApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_behaviors(self) -> list[Behavior]:
        club_id = _get_club_id()
    
        bh_list = await BehaviorRepository.list_by_club(club_id)
        return bh_list      

    async def get_behavior(self, behavior_id: uuid.UUID, club_id : uuid.UUID) -> Behavior:
        
        behavior = await BehaviorRepository(self._session).get_id_and_club(
            behavior_id=behavior_id, club_id=club_id
        )

        if behavior is None:
            raise HTTPException(
                status_code=404, detail="El comportamiento no existe"
            )

        return Behavior(id=behavior.id, name=behavior.name, code=behavior.code)
