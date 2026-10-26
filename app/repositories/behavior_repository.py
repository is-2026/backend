import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.behavior import BehaviorDB
from app.db.league import LeagueEnrollmentPlayerDB, LeagueEnrollmentDB, LeagueDB


class DuplicateNameBehavior(Exception):
    """El nombre del comportamiento no esta disponible"""

class BehaviorInUse(Exception):
    """El comportamiento esta siendo utilizado en este momento"""

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

    async def update(
        self, behavior_id: uuid.UUID, club_id: uuid.UUID, name: str, code: str
    ) -> BehaviorDB | None:
        behavior_updt = await self.get_id_and_club(behavior_id, club_id)
        if behavior_updt is None:
            return None

        behavior_updt.name = name
        behavior_updt.code = code
        try:
            await self._session.commit()
        except IntegrityError as info_exc:
            await self._session.rollback()
            raise DuplicateNameBehavior() from info_exc

        await self._session.refresh(behavior_updt)
        return behavior_updt

    async def delete(self, behavior: BehaviorDB) -> None:
        await self._session.delete(behavior)

        try:
            await self._session.commit()
        except IntegrityError as info_exc:
            await self._session.rollback()
            raise BehaviorInUse() from info_exc
        

    async def is_assigned(self, behavior_id: uuid.UUID) -> bool:
        query = (
            select(LeagueEnrollmentPlayerDB.id)
            .join(
                LeagueEnrollmentDB,
                LeagueEnrollmentDB.id == LeagueEnrollmentPlayerDB.enrollment_id,
            )
            .join(LeagueDB, LeagueDB.id == LeagueEnrollmentDB.league_id)
            .where(
                LeagueEnrollmentPlayerDB.behavior_id == behavior_id,
                LeagueDB.status == "started",
            )
            .limit(1)
        )
        return (await self._session.scalar(query)) is not None

    async def is_in_lineup(self, behavior_id: uuid.UUID) -> bool:
        query = (
            select(LeagueEnrollmentPlayerDB.id)
            .join(
                LeagueEnrollmentDB,
                LeagueEnrollmentDB.id == LeagueEnrollmentPlayerDB.enrollment_id,
            )
            .join(LeagueDB, LeagueDB.id == LeagueEnrollmentDB.league_id)
            .where(
                LeagueEnrollmentPlayerDB.behavior_id == behavior_id,
                LeagueDB.status.in_(["not_started", "started"]),
            )
            .limit(1)
        )
        return (await self._session.scalar(query)) is not None
