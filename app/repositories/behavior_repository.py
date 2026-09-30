import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.behavior import BehaviorDB


class BehaviorRepository:
    def __init__(self, session : AsyncSession) -> None:
        self.session = session

    async def list_by_club(self, club_id: uuid) -> list[BehaviorDB]:
        sel_bh_list = select(BehaviorDB).where(
            BehaviorDB.club_id == club_id  
        )
        result = await self.session.scalars(sel_bh_list)    #ejecuto la consulta
        return list(result.all())   #extraigo las filas y armo la lista

    async def get_id_and_club(
            self,
            behavior_id: uuid.UUID,
            club_id: uuid.UUID,
    )-> BehaviorDB:
        sel_id_and_clubid = select(BehaviorDB).where(  #preparo la consulta
            BehaviorDB.id == behavior_id,
            BehaviorDB.club_id == club_id
        )    
        result = await self.session.execute(sel_id_and_clubid) #envio la consulta
        return result.scalar_one_or_none() #devuelvo BehaviorDB si existe, o None si no