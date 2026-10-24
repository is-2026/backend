import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.behaviors_api_base import BaseBehaviorsApi
from app.engine.validation import InvalidBehaviorCode, validate_behavior_code
from app.models.behavior import Behavior
from app.repositories.behavior_repository import (
    BehaviorRepository,
    DuplicateNameBehavior,
)


class BehaviorApiImpl(BaseBehaviorsApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_behaviors(self, club_id: uuid.UUID) -> list[Behavior]:

        bh_list = await BehaviorRepository(self._session).list_by_club(club_id)
        return bh_list

    async def get_behavior(
        self, behavior_id: uuid.UUID, club_id: uuid.UUID
    ) -> Behavior:

        behavior = await BehaviorRepository(self._session).get_id_and_club(
            behavior_id=behavior_id, club_id=club_id
        )

        if behavior is None:
            raise HTTPException(status_code=404, detail="El comportamiento no existe")

        return Behavior(
            id=behavior.id, name=behavior.name, code=behavior.code, kind=behavior.kind
        )

    async def create_behavior(
        self, create_behavior_input, club_id: uuid.UUID
    ) -> Behavior:
        repo = BehaviorRepository(self._session)

        name = (
            create_behavior_input.name.strip()
        )  # el strip quita los espacios y saltos de linea del name
        if len(name) < 1 or len(name) > 30:
            raise HTTPException(
                status_code=400, detail="Los caracteres ingresados son invalidos"
            )
        try:
            validate_behavior_code(
                create_behavior_input.code, create_behavior_input.kind
            )
        except InvalidBehaviorCode as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        try:
            new_behavior = await repo.create(
                club_id, name, create_behavior_input.code, create_behavior_input.kind
            )
        except DuplicateNameBehavior:
            raise HTTPException(
                status_code=409, detail="El nombre ingresado no esta disponible"
            )

        return Behavior(
            id=new_behavior.id,
            name=new_behavior.name,
            code=new_behavior.code,
            kind=new_behavior.kind,
        )

    async def update_behavior(
        self, behavior_id: uuid.UUID, update_behavior_input, club_id: uuid.UUID
    ) -> Behavior:
        repo = BehaviorRepository(self._session)

        behavior = await repo.get_id_and_club(
            behavior_id, club_id
        )  # traigo todo el comportamiento
        if behavior is None:
            raise HTTPException(status_code=404, detail="El comportamiento no existe")

        if await repo.is_assigned(behavior_id):
            raise HTTPException(
                status_code=409, detail="El comportamiento esta asignado a un jugador"
            )

        name = (
            update_behavior_input.name.strip()
        )  # el strip quita los espacios y saltos de linea del name
        if len(name) < 1 or len(name) > 30:
            raise HTTPException(
                status_code=400, detail="Los caracteres ingresados son invalidos"
            )
        try:
            validate_behavior_code(update_behavior_input.code, behavior.kind)
        except InvalidBehaviorCode as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        try:
            updt_behavior = await repo.update(
                behavior_id, club_id, name, update_behavior_input.code
            )
        except DuplicateNameBehavior:
            raise HTTPException(
                status_code=409, detail="El nombre ingresado no esta disponible"
            )
        
        if updt_behavior is None:
            raise HTTPException(status_code=404, detail="El comportamiento no existe")

        return Behavior(
            id=updt_behavior.id,
            name=updt_behavior.name,
            code=updt_behavior.code,
            kind=updt_behavior.kind,
        )
