import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.behavior import BehaviorDB


class DuplicateNameBehavior(Exception):
    """El nombre del comportamiento no esta disponible"""


class BehaviorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_club(self, club_id: uuid) -> list[BehaviorDB]:
        sel_bh_list = select(BehaviorDB).where(BehaviorDB.club_id == club_id)
        result = await self._session.scalars(sel_bh_list)  # ejecuto la consulta
        return list(result.all())  # extraigo las filas y armo la lista

    async def get_id_and_club(
        self,
        behavior_id: uuid.UUID,
        club_id: uuid.UUID,
    ) -> BehaviorDB:
        sel_id_and_clubid = select(BehaviorDB).where(  # preparo la consulta
            BehaviorDB.id == behavior_id, BehaviorDB.club_id == club_id
        )
        result = await self._session.execute(sel_id_and_clubid)  # envio la consulta
        return (
            result.scalar_one_or_none()
        )  # devuelvo BehaviorDB si existe, o None si no

    async def create(
        self, club_id: uuid.UUID, name: str, code: str, kind: str
    ) -> BehaviorDB:
        behavior = BehaviorDB(
            id=uuid.uuid4(), name=name, code=code, club_id=club_id, kind=kind
        )
        self._session.add(behavior)

        try:
            await self._session.commit()
        except IntegrityError as info_exc:
            await self._session.rollback()
            raise DuplicateNameBehavior() from info_exc

        await self._session.refresh(behavior)
        return behavior
