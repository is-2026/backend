import uuid
from fastapi import HTTPException

from app.apis.behaviors_api_base import BaseBehaviorsApi
from app.models.behavior import Behavior
from app.repositories.behavior_repository import BehaviorRepository
from app.db.session import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession

def _get_club_id() -> uuid.UUID:
    # PENDIENTE: obtener el club del usuario autenticado.
    # Depende de dos cosas que todavía no existen:
    #   1. que el token llegue hasta el impl (hoy la ruta no lo pasa)
    #   2. un repositorio de Club (ticket de mi compañero)
    raise NotImplementedError("Falta obtener el club del usuario autenticado")


class DetailBehaviorApiImpl(BaseBehaviorsApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_behavior(self, behavior_id: uuid.UUID) -> Behavior:
        club_id = _get_club_id()

        
        behavior = await BehaviorRepository(self._session).get_id_and_club(
            behavior_id=behavior_id, club_id=club_id
        )

        if behavior is None:
            raise HTTPException(
                status_code=404, detail="El comportamiento no existe"
            )

        return Behavior(id=behavior.id, name=behavior.name, code=behavior.code)
