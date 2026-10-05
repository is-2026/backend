import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.player_repository import JerseyNumberUsed, PlayerRepository


async def test_create_save_player():
    
    session = MagicMock()
    session.commit = AsyncMock()

    player = await PlayerRepository(session).create(   #creo el jugador
        name= "Cavenaghi",
        number= 9,
        power= 70,
        agility= 90,
        control= 90,
        speed= 30,
        strength= 20,
        club_id= uuid.uuid4(),
    )

    session.add.assert_called_once_with(player) #comprobaciones para ver si create hizo lo que debia
    session.commit.assert_awaited_once()
    assert player.name == "Cavenaghi" # comprueba si realmente se creo
    assert player.number == 9


async def test_create_jersey_number_used_it_fail_commit():
    session = MagicMock()
    # IntegrityError es lo que lanzaría la BD si la camiseta está repetida
    session.commit = AsyncMock(
        side_effect=IntegrityError("INSERT", {}, Exception("duplicate")) #simulo el error
    )  
    session.rollback = AsyncMock()

    with pytest.raises(JerseyNumberUsed):   
        await PlayerRepository(session).create( #create va a fallar en el commit, porque hay un error de integidad 
            name="Cavenaghi",
            number=9,
            power=70,
            agility=90,
            control=90,
            speed=30,
            strength=20,
            club_id=uuid.uuid4(),
        )

  
    session.rollback.assert_awaited_once()  #confirma que el rollback ocurrio

async def test_list_players_club_returns_players():
    club_id = uuid.uuid4()
    jugadores = [MagicMock(), MagicMock()]

    result = MagicMock()  # mockeo el resultado
    result.scalars.return_value.all.return_value = jugadores

    session = MagicMock() 
    session.execute = AsyncMock(return_value=result)

    players = await PlayerRepository(session).list_players_club(club_id)

    assert players == jugadores
    session.execute.assert_awaited_once()

async def test_list_players_club_empty():
    club_id = uuid.uuid4()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    players = await PlayerRepository(session).list_players_club(club_id)

    assert players == []

#Ejecutar test con : python -m pytest tests/repositories -v