import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from app.impl import friendlies_api_impl
from app.impl.friendlies_api_impl import FriendliesApiImpl, _validate_squad
from app.models.create_friendly_input import CreateFriendlyInput
from app.models.join_friendly_input import JoinFriendlyInput
from app.models.squad_player_input import SquadPlayerInput
from app.repositories.friendly_repository import FriendlyUnavailable, InvalidSquad


CANT_JUGADORES = 6
CLUB_CREATOR = uuid.uuid4()
CLUB_RIVAL = uuid.uuid4()
CLUB_NAMES = {CLUB_CREATOR: "Boca", CLUB_RIVAL: "River"}

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

#test con 3 titulares y < 3 suplentes, no se puede porque no se puede armar un friendly directamente. Ademas no lo chequearia

@pytest.fixture
def mocks(monkeypatch):
    m = SimpleNamespace() #es como una caja que le vas colgando atributos
    m.friendly_repo = AsyncMock()
    m.player_repo = AsyncMock()
    m.lobby = AsyncMock()
    m.hash_password = AsyncMock(return_value="hashed")
    m.verify_password = AsyncMock(return_value=True)
 
    m.player_repo.count_club_players.return_value = CANT_JUGADORES #la cant de jugadores por repo es 6
    # nombre de cada club según su id
    m.friendly_repo.get_club_name.side_effect = CLUB_NAMES.get
 
    monkeypatch.setattr(friendlies_api_impl, "FriendlyRepository", MagicMock(return_value=m.friendly_repo)) #mockeo, reemplazo lo que espera por mis mocks 
    monkeypatch.setattr(friendlies_api_impl, "PlayerRepository", MagicMock(return_value=m.player_repo))
    monkeypatch.setattr(friendlies_api_impl, "hash_password", m.hash_password)
    monkeypatch.setattr(friendlies_api_impl, "verify_password", m.verify_password)
    return m

@pytest.fixture
def api(mocks): #lo que vamos a testear
    impl = FriendliesApiImpl(session=MagicMock(), lobby_manager=mocks.lobby)
    impl._schedule_start = MagicMock()  # schedule_start es lo que crea el timer del lobby, como no lo queremos ponemos un mock
    return impl
 
 
def friendly_waiting(hashed_password=None):
    """Lo que devolvería el repo para un friendly que espera rival."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        creator_club_id=CLUB_CREATOR,
        status="waiting_for_rival",
        hashed_password=hashed_password,
    )
def friendly_accepted(friendly, hashed_password=None):
    """Lo que devuelve repo.accept junto con el match."""
    return SimpleNamespace(
        id=friendly.id,
        creator_club_id=CLUB_CREATOR,
        status="accepted",
        hashed_password=hashed_password,
    )
 
async def test_create_friendly_public(api, mocks): 
    mocks.friendly_repo.create.return_value = SimpleNamespace(
        id=uuid.uuid4(), creator_club_id=CLUB_CREATOR, status="waiting_for_rival"
    )
 
    result = await api.create_friendly(CreateFriendlyInput(players=make_squad(3)), CLUB_CREATOR)
 
    mocks.hash_password.assert_not_awaited()  # sin contraseña no se hashea nada
    assert result.is_private is False
    assert result.rival_club_id is None
    assert result.creator_club_name == "Boca"
 
 
async def test_create_friendly_private(api, mocks):
    mocks.friendly_repo.create.return_value = SimpleNamespace(
        id=uuid.uuid4(), creator_club_id=CLUB_CREATOR, status="waiting_for_rival"
    )
 
    result = await api.create_friendly(
        CreateFriendlyInput(players=make_squad(3), password="1234"), CLUB_CREATOR
    )
 
    mocks.hash_password.assert_awaited_once_with("1234")
    assert result.is_private is True
 
 
async def test_create_friendly_players_other_club(api, mocks):
    mocks.player_repo.count_club_players.return_value = 5  # uno no es del club
 
    with pytest.raises(HTTPException) as error:
        await api.create_friendly(CreateFriendlyInput(players=make_squad(3)), CLUB_CREATOR)
 
    assert error.value.status_code == 400
    mocks.friendly_repo.create.assert_not_awaited()  # no se llegó a crear nada
 
 
async def test_create_friendly_squad_invalid(api, mocks):
    mocks.friendly_repo.create.side_effect = InvalidSquad()  # el repo falla
 
    with pytest.raises(HTTPException) as error:
        await api.create_friendly(CreateFriendlyInput(players=make_squad(3)), CLUB_CREATOR)
 
    assert error.value.status_code == 400
 


async def test_join_friendly_not_exist(api, mocks):
    mocks.friendly_repo.get.return_value = None
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            uuid.uuid4(), JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
        )
 
    assert error.value.status_code == 404
 
 
async def test_join_friendly_not_available(api, mocks):
    friendly = friendly_waiting()
    friendly.status = "accepted"  # ya tiene rival
    mocks.friendly_repo.get.return_value = friendly
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
        )
 
    assert error.value.status_code == 409
 
 
async def test_join_own_friendly(api, mocks):
    friendly = friendly_waiting()
    mocks.friendly_repo.get.return_value = friendly
 
    with pytest.raises(HTTPException) as error:
        # entra el mismo club que lo creó
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_CREATOR
        )
 
    assert error.value.status_code == 409
 
async def test_join_friendly_private_without_password(api, mocks):
    friendly = friendly_waiting(hashed_password="hashed")
    mocks.friendly_repo.get.return_value = friendly
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
        )
 
    assert error.value.status_code == 400
    mocks.friendly_repo.accept.assert_not_awaited()
 

 
async def test_join_friendly_password_incorrect(api, mocks):
    friendly = friendly_waiting(hashed_password="hashed")
    mocks.friendly_repo.get.return_value = friendly
    mocks.verify_password.return_value = False  # la contraseña no coincide
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3), password="mala"), CLUB_RIVAL
        )
 
    assert error.value.status_code == 400
    mocks.friendly_repo.accept.assert_not_awaited()
 
 
async def test_join_friendly_squad_invalid(api, mocks):
    friendly = friendly_waiting()
    mocks.friendly_repo.get.return_value = friendly
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(2)), CLUB_RIVAL  # solo 2 titulares
        )
 
    assert error.value.status_code == 400
    mocks.friendly_repo.accept.assert_not_awaited()
 
 
async def test_join_friendly_players_other_club(api, mocks):
    friendly = friendly_waiting()
    mocks.friendly_repo.get.return_value = friendly
    mocks.player_repo.count_club_players.return_value = 5
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
        )
 
    assert error.value.status_code == 400
    mocks.friendly_repo.accept.assert_not_awaited()
 
 
async def test_join_friendly_other_user_joined_first(api, mocks):
    friendly = friendly_waiting()
    mocks.friendly_repo.get.return_value = friendly
    mocks.friendly_repo.accept.side_effect = FriendlyUnavailable()
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
        )
 
    assert error.value.status_code == 409
    mocks.lobby.broadcast.assert_not_awaited()  # si falla no se avisa a nadie
    api._schedule_start.assert_not_called()
 
 
async def test_join_friendly_repo_squad_invalid(api, mocks):
    friendly = friendly_waiting()
    mocks.friendly_repo.get.return_value = friendly
    mocks.friendly_repo.accept.side_effect = InvalidSquad()
 
    with pytest.raises(HTTPException) as error:
        await api.join_friendly(
            friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
        )
 
    assert error.value.status_code == 400
    mocks.lobby.broadcast.assert_not_awaited()

 
 
async def test_join_friendly_ok(api, mocks):
    friendly = friendly_waiting()
    match = SimpleNamespace(id=uuid.uuid4())
    mocks.friendly_repo.get.return_value = friendly
    mocks.friendly_repo.accept.return_value = (
        SimpleNamespace(
            id=friendly.id,
            creator_club_id=CLUB_CREATOR,
            status="accepted",
            hashed_password=None,
        ),
        match,
    )
 
    result = await api.join_friendly(
        friendly.id, JoinFriendlyInput(players=make_squad(3)), CLUB_RIVAL
    )
 
    # 1. devuelve el friendly con rival y match
    assert result.rival_club_id == CLUB_RIVAL
    # el nombre del creador, no el del que se une
    assert result.creator_club_name == "Boca"
    assert result.match_id == match.id
 
    # 2. avisó por websocket
    mocks.lobby.broadcast.assert_awaited_once()
    channel, massage = mocks.lobby.broadcast.await_args.args
    assert channel == friendly.id
    assert massage["type"] == "friendlyClubRegistered"
    assert massage["data"]["club_name"] == "River"
 
    # 3. agendó el inicio del match
    api._schedule_start.assert_called_once_with(friendly.id, match.id)
 
async def test_join_friendly_private_correct_password(api, mocks):
    friendly = friendly_waiting(hashed_password="hashed")
    match = SimpleNamespace(id=uuid.uuid4())
    mocks.friendly_repo.get.return_value = friendly
    mocks.friendly_repo.accept.return_value = (friendly_accepted(friendly, "hashed"), match)
 
    result = await api.join_friendly(
        friendly.id, JoinFriendlyInput(players=make_squad(3), password="1234"), CLUB_RIVAL
    )
 
    mocks.verify_password.assert_awaited_once_with("1234", "hashed")
    assert result.is_private is True
    assert result.match_id == match.id

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
    mocked_repo.get_club_names = AsyncMock(
        return_value={club_id_1: "Boca", club_id_2: "River"}
    )
    
    # Configuramos el comportamiento del método is_private
    def mock_is_private(f):
        return f == mock_friendly_2  # El primero es público, el segundo privado
    mocked_repo.is_private.side_effect = mock_is_private
    
    mocked_repo_class.return_value = mocked_repo

    # Listamos amistosos
    api = FriendliesApiImpl(MagicMock(), lobby_manager=MagicMock())
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

    assert result[0].creator_club_name == "Boca"
    assert result[1].creator_club_name == "River"
    mocked_repo.get_club_names.assert_awaited_once_with([club_id_1, club_id_2])
    
    mocked_repo.list_available_friendlies.assert_awaited_once()


@patch("app.impl.friendlies_api_impl.FriendlyRepository")
async def test_list_friendlies_returns_empty(mocked_repo_class):
    mocked_repo = MagicMock()

    # sin amistosos disponibles
    mocked_repo.list_available_friendlies = AsyncMock(return_value=[])
    mocked_repo_class.return_value = mocked_repo

    # listamos amistosos
    api = FriendliesApiImpl(MagicMock(), lobby_manager=MagicMock())
    result = await api.list_friendlies()

    assert result == []
    # sin amistosos no consulta los nombres
    mocked_repo.get_club_names.assert_not_called()
    mocked_repo.list_available_friendlies.assert_awaited_once()
