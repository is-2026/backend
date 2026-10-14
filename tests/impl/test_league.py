import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.db.player import PlayerDB
from app.db.user import UserDB
from app.impl import league_api_impl
from app.impl.league_api_impl import LeaguesApiImpl
from app.models.create_league_input import CreateLeagueInput
from app.models.squad_player_input import SquadPlayerInput
from app.security.tokens import create_access_token

CLUB = SimpleNamespace(id=uuid.uuid4(), club_name="River Plate")


def make_input(starters=3, password=None):
    players = [
        SquadPlayerInput(
            player_id=uuid.uuid4(),
            is_starter=i < starters,
            behavior_id=uuid.uuid4() if i < starters else None,
        )
        for i in range(6)
    ]
    return CreateLeagueInput(
        name="Liga", 
        password=password, 
        max_clubs=5,
        match_duration_minutes=10, 
        players=players,
    )


@pytest.fixture
def mocks(monkeypatch):
    mock = SimpleNamespace()
    mock.session = MagicMock()
    mock.session.get = AsyncMock(return_value=SimpleNamespace(club_id=CLUB.id))
    mock.player_repo = AsyncMock()
    mock.player_repo.count_club_players.return_value = 6  # los 6 son del club
    mock.league_repo = AsyncMock()
    mock.league_repo.create_with_enrollment.return_value = SimpleNamespace(
        id=uuid.uuid4(), 
        name="LPF Chiqui Mafia", 
        hashed_password=None,
        max_clubs=5, 
        status="not_started",
    )
    mock.hash_password = AsyncMock(return_value="hashed")

    monkeypatch.setattr(league_api_impl, "PlayerRepository", MagicMock(return_value=mock.player_repo)) #Seteo lo que mockee
    monkeypatch.setattr(league_api_impl, "LeagueRepository", MagicMock(return_value=mock.league_repo))
    monkeypatch.setattr(league_api_impl, "hash_password", mock.hash_password)
    return mock


@pytest.fixture
def api(mocks):  #Aca directamente mockeo toda la clase, porque la voy a necesitar para los tests.
    return LeaguesApiImpl(mocks.session)


async def test_create_league_public(api, mocks):
    result = await api.create_league(make_input(), CLUB)

    mocks.hash_password.assert_not_awaited()  # sin password no se hashea
    assert result.is_private is False
    assert result.status == "not_started"
    # el creador queda inscripto
    assert result.registered_clubs[0].club_id == CLUB.id
    assert result.registered_clubs[0].club_name == "River Plate"
    assert mocks.league_repo.create_with_enrollment.await_args.kwargs["club_id"] == CLUB.id


async def test_create_league_private(api, mocks):
    mocks.league_repo.create_with_enrollment.return_value.hashed_password = "hashed"

    result = await api.create_league(make_input(password="1234"), CLUB)

    mocks.hash_password.assert_awaited_once_with("1234")
    assert result.is_private is True


@pytest.mark.parametrize("starters", [2, 4])
async def test_create_league_wrong_number_of_starters(api, mocks, starters):
    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(starters=starters), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_starter_without_behavior(api, mocks):
    data = make_input()
    data.players[0].behavior_id = None

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_repeated_players(api, mocks):
    data = make_input()
    data.players[1].player_id = data.players[0].player_id

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_players_other_club(api, mocks):
    mocks.player_repo.count_club_players.return_value = 5  # uno no es del club

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_behavior_other_club(api, mocks):
    mocks.session.get.return_value = SimpleNamespace(club_id=uuid.uuid4())  # club ajeno

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_behavior_not_exist(api, mocks):
    mocks.session.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400


async def test_create_league_repo_integrity_error(api, mocks):
    mocks.league_repo.create_with_enrollment.side_effect = IntegrityError("INSERT", {}, Exception("fk"))

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400

@pytest.mark.parametrize("max_clubs", [21, 30])
async def test_create_league_max_clubs_over_limit(api, mocks, max_clubs):
    data = make_input()
    data.max_clubs = max_clubs  # Pydantic lo acepta (le=30), el límite real lo pone el impl

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_max_clubs_at_limit(api, mocks):
    data = make_input()
    data.max_clubs = 20

    result = await api.create_league(data, CLUB)

    assert result.max_clubs == 5  # lo que devuelve el repo mockeado
    mocks.league_repo.create_with_enrollment.assert_awaited_once()

async def test_get_league_public(api, mocks):

    league = SimpleNamespace(id = uuid.uuid4(),
                            name = "LPF chiqui Mafia",
                            hashed_password= None,
                            max_clubs= 5,
                            status = "not_started")

    club = SimpleNamespace(id = uuid.uuid4(),
                           club_name = "River Plate")
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = [club]

    result = await api.get_league(league.id)

    assert result.id == league.id
    assert result.name == "LPF chiqui Mafia"
    assert result.is_private is False
    assert result.status == "not_started"
    assert result.registered_clubs[0].club_name == "River Plate"
    
    mocks.league_repo.get.assert_awaited_once_with(league.id) #busco la liga 

async def test_get_league_private(api,mocks):
    league = SimpleNamespace(id = uuid.uuid4(),
                                name = "LPF chiqui Mafia",
                                hashed_password= "password",
                                max_clubs= 5,
                                status = "not_started")
    club = SimpleNamespace(id = uuid.uuid4(),
                               club_name = "River Plate")
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = [club]

    result = await api.get_league(league.id)

    assert result.id == league.id
    assert result.name == "LPF chiqui Mafia"
    assert result.is_private is True
    assert result.status == "not_started"
    assert result.registered_clubs[0].club_name == "River Plate"

@pytest.mark.parametrize("status", ["started","finished"])
async def test_get_league_not_available(api, mocks, status):
    league = SimpleNamespace(id = uuid.uuid4(),
                                    name = "LPF chiqui Mafia",
                                    hashed_password= "password",
                                    max_clubs= 5,
                                    status = status)
    
    mocks.league_repo.get.return_value = league 

    with pytest.raises(HTTPException) as error: #basicamente digo, lo que viene tiene que ser una excepcion, y lo guardo en error
        await api.get_league(league.id)

    assert error.value.status_code == 404
#test listar ligas
async def test_list_leagues_public(api, mocks):
    league = SimpleNamespace(id=uuid.uuid4(), name="Liga", hashed_password=None,
                             max_clubs=5, status="not_started")
    club = SimpleNamespace(id=uuid.uuid4(), club_name="River")
    mocks.league_repo.list_not_started.return_value = [league]
    mocks.league_repo.list_clubs_of_league.return_value = [club]

    result = await api.list_leagues()

    assert len(result) == 1
    assert result[0].id == league.id
    assert result[0].name == "Liga"
    assert result[0].is_private is False
    assert result[0].status == "not_started"
    assert result[0].registered_clubs[0].club_name == "River"
    mocks.league_repo.list_clubs_of_league.assert_awaited_once_with(league.id)


async def test_list_leagues_private(api, mocks):
    league = SimpleNamespace(id=uuid.uuid4(), name="Liga", hashed_password="hash",
                             max_clubs=5, status="not_started")
    mocks.league_repo.list_not_started.return_value = [league]
    mocks.league_repo.list_clubs_of_league.return_value = []

    result = await api.list_leagues()

    assert result[0].is_private is True
    assert result[0].registered_clubs == []


async def test_list_leagues_empty(api, mocks):
    mocks.league_repo.list_not_started.return_value = []

    result = await api.list_leagues()

    assert result == []
    mocks.league_repo.list_clubs_of_league.assert_not_awaited()

#tests de endpoint

URL = "/leagues"


@pytest.fixture
async def club(session):
    """Crea un usuario y su club reales en la base de test."""
    user_id = uuid.uuid4()
    club_id = uuid.uuid4()
    session.add(UserDB(id=user_id, email="hola@prueba.com", hashed_password="hash"))
    await session.flush()  # el usuario se inserta antes que el club
    session.add(
        ClubDB(
            id=club_id,
            club_name="Instituto",
            avatar_url="https://img.com/avatar.png",
            user_id=user_id,
        )
    )
    await session.commit()
    return SimpleNamespace(id=club_id, user_id=user_id)


def auth_header(club) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(club.user_id)}"}


async def count_leagues(session) -> int:
    return await session.scalar(select(func.count()).select_from(LeagueDB))


async def make_body(session, club) -> dict:
    """Body válido: 6 jugadores y 3 comportamientos reales del club."""
    players = []
    for i in range(6):
        players.append(
            PlayerDB(
                id=uuid.uuid4(), name=f"Jugador {i}", number=i + 1,
                power=100, agility=100, control=30, speed=30, strength=40,
                club_id=club.id,
            )
        )
    behaviors = []
    for i in range(3):
        behaviors.append(
            BehaviorDB(
                id=uuid.uuid4(), name=f"Comp {i}",
                code="def decide_action(): pass", club_id=club.id,
            )
        )
    session.add_all(players + behaviors)
    await session.commit()

    squad = []
    for i, player in enumerate(players):
        if i < 3:
            squad.append(
                {"player_id": str(player.id), "is_starter": True,
                 "behavior_id": str(behaviors[i].id)}
            )
        else:
            squad.append(
                {"player_id": str(player.id), "is_starter": False, "behavior_id": None}
            )
    return {
        "name": "Mi liga",
        "max_clubs": 5,
        "match_duration_minutes": 10,
        "players": squad,
    }


async def add_league(session, club, name, status, password=None):
    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id, name=name, hashed_password=password, max_clubs=5,
            match_duration_minutes=10, status=status, creator_club_id=club.id,
        )
    )
    await session.commit()  # primero la liga, después la inscripción (clave foránea)
    session.add(LeagueEnrollmentDB(id=uuid.uuid4(), league_id=league_id, club_id=club.id))
    await session.commit()


# --- POST /leagues (crear liga) ---
async def test_endpoint_create_league_returns_201(client, session, club):
    body = await make_body(session, club)

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 201
    data = r.json()
    uuid.UUID(data["id"])  # ver si es uuid
    assert data["name"] == "Mi liga"
    assert data["is_private"] is False
    assert data["status"] == "not_started"
    assert data["max_clubs"] == 5
    assert data["registered_clubs"][0]["club_name"] == "Instituto"
    assert await count_leagues(session) == 1
    inscripciones = await session.scalar(select(func.count()).select_from(LeagueEnrollmentDB))
    jugadores = await session.scalar(select(func.count()).select_from(LeagueEnrollmentPlayerDB))
    assert inscripciones == 1  # el creador queda inscripto
    assert jugadores == 6


async def test_endpoint_create_league_with_password_is_private(client, session, club):
    body = await make_body(session, club)
    body["password"] = "1234"

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 201
    assert r.json()["is_private"] is True


async def test_endpoint_create_league_max_clubs_at_limit(client, session, club):
    body = await make_body(session, club)
    body["max_clubs"] = 20

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 201
    assert r.json()["max_clubs"] == 20


async def test_endpoint_create_league_max_clubs_over_limit(client, session, club):
    body = await make_body(session, club)
    body["max_clubs"] = 21

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert "message" in r.json()
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_max_clubs_too_low(client, session, club):
    body = await make_body(session, club)
    body["max_clubs"] = 2

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_only_5_players(client, session, club):
    body = await make_body(session, club)
    body["players"].pop()

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_only_2_starters(client, session, club):
    body = await make_body(session, club)
    body["players"][2]["is_starter"] = False

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_starter_without_behavior(client, session, club):
    body = await make_body(session, club)
    body["players"][0]["behavior_id"] = None

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_missing_name(client, session, club):
    body = await make_body(session, club)
    del body["name"]

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_behavior_of_other_club(client, session, club):
    body = await make_body(session, club)

    # creo otro club con un comportamiento propio
    other_user_id = uuid.uuid4()
    other_club_id = uuid.uuid4()
    other_behavior_id = uuid.uuid4()
    session.add(UserDB(id=other_user_id, email="otro@prueba.com", hashed_password="hash"))
    await session.flush()
    session.add(
        ClubDB(id=other_club_id, club_name="Otro club",
               avatar_url="https://img.com/avatar.png", user_id=other_user_id)
    )
    await session.commit()
    session.add(
        BehaviorDB(id=other_behavior_id, name="Ajeno",
                   code="def decide_action(): pass", club_id=other_club_id)
    )
    await session.commit()

    body["players"][0]["behavior_id"] = str(other_behavior_id)

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert "message" in r.json()
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_without_token_returns_401(client, session, club):
    body = await make_body(session, club)

    r = await client.post(URL, json=body)

    assert r.status_code == 401
    assert "message" in r.json()
    assert await count_leagues(session) == 0


# --- GET /leagues (listar ligas) ---
async def test_endpoint_list_leagues_returns_only_not_started(client, session, club):
    await add_league(session, club, "Liga publica", "not_started")
    await add_league(session, club, "Liga privada", "not_started", password="hash")
    await add_league(session, club, "Liga iniciada", "started")
    await add_league(session, club, "Liga terminada", "finished")

    r = await client.get(URL, headers=auth_header(club))

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for league in data:
        assert league["status"] == "not_started"
        assert league["registered_clubs"][0]["club_name"] == "Instituto"
        if league["name"] == "Liga publica":
            assert league["is_private"] is False
        else:
            assert league["name"] == "Liga privada"
            assert league["is_private"] is True


async def test_endpoint_list_leagues_empty(client, session, club):
    r = await client.get(URL, headers=auth_header(club))

    assert r.status_code == 200
    assert r.json() == []


async def test_endpoint_list_leagues_without_token_returns_401(client, session):
    r = await client.get(URL)

    assert r.status_code == 401
    assert "message" in r.json()
