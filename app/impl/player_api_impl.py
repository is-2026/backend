import uuid 

from fastapi import HTTPException

from app.apis.players_api_base import BasePlayersApi
from app.db.session import SessionLocal
from app.models.create_player_input import CreatePlayerInput
from app.models.player import Player
from app.repositories.player_repository import JerseyNumberUsed, PlayerRepository

PACSS_TOTAL = 300

def _validate_player(data : CreatePlayerInput) -> None:
    pacss = [
        data.power,
        data.agility,
        data.control,
        data.speed,
        data.strength
    ]
    if sum(pacss) != PACSS_TOTAL:
        raise HTTPException(status_code=400, detail="La suma de los PACSS no es 300")



class PlayerApiImpl(BasePlayersApi):
    async def create_player(
                            self,
                            create_player_input: CreatePlayerInput,
                            club_id : uuid.UUID
                           ) -> Player: 
        _validate_player(create_player_input)
       
        async with SessionLocal() as session:
            try: 
                player= await PlayerRepository(session).create(
                    name= create_player_input.name,
                    number= create_player_input.number,
                    power= create_player_input.power,
                    agility= create_player_input.agility,
                    control= create_player_input.control,
                    speed= create_player_input.speed,
                    strength= create_player_input.strength,
                    club_id= club_id
                )   
            except JerseyNumberUsed as dep:
                raise HTTPException(status_code=409, detail="El número de camiseta ya está en uso") from dep
            return Player(
                id= player.id,
                name= player.name,
                number=player.number,
                power=player.power,
                agility=player.agility,
                control=player.control,
                speed=player.speed,
                strength=player.strength,
            )

