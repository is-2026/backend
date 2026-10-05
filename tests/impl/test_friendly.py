import uuid

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from app.impl.friendlies_api_impl import FriendliesApiImpl, _validate_squad
from app.models.squad_player_input import SquadPlayerInput

CANT_JUGADORES = 6

def make_squad( starters : int, total : int = CANT_JUGADORES) -> list[SquadPlayerInput]:
    return[
        SquadPlayerInput(
            player_id= uuid.uuid4(),
            is_starter= rango < starters,
            behavior_id=uuid.uuid4() if rango < starters else None
        )
        for rango in range(total)
    ]

def test_validate_squad_accept_3_tit_and_3_sust():
    assert _validate_squad(make_squad(starters=3)) is None   #si pasa validate_squad retorna None, sino lanza un assert


@pytest.mark.parametrize("starters", [0,1,2,4,5,6])
def test_validate_squad_error_titulares(starters):
    with pytest.raises(HTTPException) as exc_info:
        _validate_squad(make_squad(starters= starters))
    assert exc_info.value.status_code == 400


#def test_validate_squad_error_1_titulares():
#    with pytest.raises(HTTPException) as exc_info:
#        _validate_squad(make_squad(starters=1))
#    assert exc_info.value.status_code == 400

#test con 3 titulares y < 3 suplentes, no se puede porque no se puede armar un amistoso directamente. Ademas no lo chequearia

@patch("app.impl.friendlies_api_impl.FriendlyRepository")
async def test_list_friendlies_returns_list(mocked_repo_class):
    mocked_repo = MagicMock()
    
    # Valores de prueba
    friendly_id_1 = uuid.uuid4()
    club_id_1 = uuid.uuid4()
    friendly_id_2 = uuid.uuid4()
    club_id_2 = uuid.uuid4()

    # Creamos amistosos mockeados con los atributos que lee el endpoint
    mock_friendly_1 = MagicMock()
    mock_friendly_1.id = friendly_id_1
    mock_friendly_1.creator_club_id = club_id_1
    mock_friendly_1.rival_club_id = None
    mock_friendly_1.status = "waiting_for_rival"
    mock_friendly_1.match_id = None

    mock_friendly_2 = MagicMock()
    mock_friendly_2.id = friendly_id_2
    mock_friendly_2.creator_club_id = club_id_2
    mock_friendly_2.rival_club_id = None
    mock_friendly_2.status = "waiting_for_rival"
    mock_friendly_2.match_id = None

    fake_list = [mock_friendly_1, mock_friendly_2]
    
    # Configuramos el mock del repositorio
    mocked_repo.list_available_friendlies = AsyncMock(return_value=fake_list)
    
    # Configuramos el comportamiento del método is_private
    def mock_is_private(f):
        return f == mock_friendly_2  # El primero es público, el segundo privado
    mocked_repo.is_private.side_effect = mock_is_private
    
    mocked_repo_class.return_value = mocked_repo

    # Listamos amistosos
    api = FriendliesApiImpl(MagicMock())
    result = await api.list_friendlies()

    # Comprobamos la respuesta mapeada a los modelos Pydantic
    assert len(result) == 2
    
    assert result[0].id == friendly_id_1
    assert result[0].creator_club_id == club_id_1
    assert result[0].is_private is False
    assert result[0].status == "waiting_for_rival"

    assert result[1].id == friendly_id_2
    assert result[1].creator_club_id == club_id_2
    assert result[1].is_private is True
    assert result[1].status == "waiting_for_rival"
    
    mocked_repo.list_available_friendlies.assert_awaited_once()


@patch("app.impl.friendlies_api_impl.FriendlyRepository")
async def test_list_friendlies_returns_empty(mocked_repo_class):
    mocked_repo = MagicMock()

    # sin amistosos disponibles
    mocked_repo.list_available_friendlies = AsyncMock(return_value=[])
    mocked_repo_class.return_value = mocked_repo

    # listamos amistosos
    api = FriendliesApiImpl(MagicMock())
    result = await api.list_friendlies()

    assert result == []
    mocked_repo.list_available_friendlies.assert_awaited_once()