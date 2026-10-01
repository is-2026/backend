import pytest
import uuid
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from app.impl.player_api_impl import PlayerApiImpl
from app.models.create_player_input import CreatePlayerInput
from app.repositories.player_repository import JerseyNumberUsed
from app.impl.player_api_impl import _validate_player  
from app.models.create_player_input import CreatePlayerInput

def test_validate_sum_300():
    player_data = CreatePlayerInput(
    name= "Cavenaghi",
    number= 9,
    power= 70,
    agility=90,
    control=90,
    speed=30,
    strength=20
        )

    assert _validate_player(player_data) is None

def test_validate_sum_not300():
    player_data = CreatePlayerInput(
    name= "Paredes",
    number= 5,
    power= 20,
    agility=20,
    control=20,
    speed=20,
    strength=20    

        )
    with pytest.raises(HTTPException) as exc_info: #ejecuta lo que esta en _validate_player y agarra la excepcion guardandola en exc_info
        _validate_player(player_data)

    assert exc_info.value.status_code == 400  #para ver el codigo de la excepcion
    assert exc_info.value.detail == "La suma de los PACSS no es 300"  #para ver el detalle

# Los parámetros llegan de abajo hacia arriba: SessionLocal, PlayerRepository
@patch("app.impl.player_api_impl.PlayerRepository")
@patch("app.impl.player_api_impl.SessionLocal")
async def test_create_player_jersey_used(
    mocked_session_local,
    mocked_repo_class,
):
    club_id = uuid.uuid4()
    mocked_repo = MagicMock() #el objeto que devuelve PlayerRepository dsp de la interaccion con la session (create es async)

    mocked_repo.create = AsyncMock(side_effect=JerseyNumberUsed(9)) #AsyncMock solo lo usamos cuando necesitamos un await (create es async)

    mocked_repo_class.return_value = mocked_repo  #conecto la clase falsa con el objeto falso

    player_data = CreatePlayerInput(
        name= "Cavenaghi",
        number= 9,
        power= 70,
        agility=90,
        control=90,
        speed=30,
        strength=20
    )

    with pytest.raises(HTTPException) as exc_info:
        await PlayerApiImpl().create_player(player_data, club_id)

    assert exc_info.value.status_code == 409

