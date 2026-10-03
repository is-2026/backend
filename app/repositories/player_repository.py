import uuid

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.player import PlayerDB


class JerseyNumberUsed(Exception):
    """El número de camiseta de jugador está en uso."""


class PlayerRepository:
    def __init__(self, session : AsyncSession) -> None: #arranca una session asincrona de SQLAlchemy
        self.session = session

    async def create(self,  
                    name: str,
                    number: int,
                    power: int,
                    agility: int,   
                    control: int,
                    speed: int,
                    strength: int,
                    club_id: uuid.UUID
                    ) -> PlayerDB:
        player = PlayerDB(id=uuid.uuid4(),    #armo el objeto
                          name=name,
                          number=number,
                          power=power,
                          agility=agility,
                          control=control,
                          speed=speed,
                          strength=strength,
                          club_id=club_id   
                         )
        
        self.session.add(player) #añado el objeto a la session

        try:
            await self.session.commit() #Ejecuto el insert a la bd

        except IntegrityError as dep:
            await self.session.rollback() #hace un rollback a la session para "limpiarla" y poder seguir usandola
            raise JerseyNumberUsed(number) from dep #Lanzo la excepcion 
        return player

        

    async def count_club_players(
        self,
        club_id: uuid.UUID,
        player_ids: list[uuid.UUID],
    ) -> int:
        # cuenta cuántos de esos ids existen Y son de este club
        result = await self.session.execute(
            select(func.count()).select_from(PlayerDB)
            .where(PlayerDB.club_id == club_id, PlayerDB.id.in_(player_ids))
        )
        return result.scalar_one()
    