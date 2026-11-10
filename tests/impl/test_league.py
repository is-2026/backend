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
from app.db.match import MatchDB, MatchStatus
from app.db.player import PlayerDB
from app.db.standings import LeagueStandingsDB
from app.db.user import UserDB
from app.repositories.league_repository import (
    ClubAlreadyEnrolled,
    ClubNotEnrolled,
    LeagueStartFailure,
)
from app.impl import league_api_impl
from app.impl.league_api_impl import LeaguesApiImpl
from app.models.create_league_input import CreateLeagueInput
from app.models.join_league_input import JoinLeagueInput
from app.models.squad_player_input import SquadPlayerInput
from app.models.submit_lineup_input import SubmitLineupInput
from app.security.tokens import create_access_token

CLUB = SimpleNamespace(id=uuid.uuid4(), club_name="River Plate")


def make_create_league_input(starters=3, password=None):
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
        formation="TRIANGLE",
        players=players,
    )


def make_join_league_input(starters=3, password=None):
    players = [
        SquadPlayerInput(
            player_id=uuid.uuid4(),
            is_starter=i < starters,
            behavior_id=uuid.uuid4() if i < starters else None,
        )
        for i in range(6)
    ]
    return JoinLeagueInput(
        password=password,
        formation="TRIANGLE",
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
        allows_draws=True,
    )
    mock.hash_password = AsyncMock(return_value="hashed")
    mock.verify_password = AsyncMock(return_value=True)
    mock.lobby_connection = MagicMock()
    mock.lobby_connection.broadcast = AsyncMock()
    mock.lobby_connection.close_all = AsyncMock()
    mock.league_scheduler = MagicMock()
    mock.match_repo = AsyncMock()

    monkeypatch.setattr(
        league_api_impl, "PlayerRepository", MagicMock(return_value=mock.player_repo)
    )  # Seteo lo que mockee
    monkeypatch.setattr(
        league_api_impl, "LeagueRepository", MagicMock(return_value=mock.league_repo)
    )
    monkeypatch.setattr(
        league_api_impl, "MatchRepository", MagicMock(return_value=mock.match_repo)
    )
    monkeypatch.setattr(league_api_impl, "hash_password", mock.hash_password)
    monkeypatch.setattr(league_api_impl, "verify_password", mock.verify_password)

    monkeypatch.setattr(
        league_api_impl, "league_lobby_connection", mock.lobby_connection
    )  # mockeamos el lobby de ligas

    return mock


@pytest.fixture
def api(
    mocks,
):  # Aca directamente mockeo toda la clase, porque la voy a necesitar para los tests.
    return LeaguesApiImpl(mocks.session, mocks.league_scheduler)


async def test_create_league_public(api, mocks):
    result = await api.create_league(make_create_league_input(), CLUB)

    mocks.hash_password.assert_not_awaited()  # sin password no se hashea
    assert result.is_private is False
    assert result.status == "not_started"
    # el creador queda inscripto
    assert result.registered_clubs[0].club_id == CLUB.id
    assert result.registered_clubs[0].club_name == "River Plate"
    assert (
        mocks.league_repo.create_with_enrollment.await_args.kwargs["club_id"] == CLUB.id
    )


async def test_create_league_saves_formation(api, mocks):
    data = make_create_league_input()
    data.formation = "DEFENSIVE_LINE"

    await api.create_league(data, CLUB)

    assert (
        mocks.league_repo.create_with_enrollment.await_args.kwargs["formation"]
        == "DEFENSIVE_LINE"
    )


async def test_create_league_private(api, mocks):
    mocks.league_repo.create_with_enrollment.return_value.hashed_password = "hashed"

    result = await api.create_league(make_create_league_input(password="1234"), CLUB)

    mocks.hash_password.assert_awaited_once_with("1234")
    assert result.is_private is True


@pytest.mark.parametrize("starters", [2, 4])
async def test_create_league_wrong_number_of_starters(api, mocks, starters):
    with pytest.raises(HTTPException) as error:
        await api.create_league(make_create_league_input(starters=starters), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_starter_without_behavior(api, mocks):
    data = make_create_league_input()
    data.players[0].behavior_id = None

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_repeated_players(api, mocks):
    data = make_create_league_input()
    data.players[1].player_id = data.players[0].player_id

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_players_other_club(api, mocks):
    mocks.player_repo.count_club_players.return_value = 5  # uno no es del club

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_create_league_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_behavior_other_club(api, mocks):
    mocks.session.get.return_value = SimpleNamespace(club_id=uuid.uuid4())  # club ajeno

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_create_league_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_behavior_not_exist(api, mocks):
    mocks.session.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_create_league_input(), CLUB)

    assert error.value.status_code == 400


async def test_create_league_repo_integrity_error(api, mocks):
    mocks.league_repo.create_with_enrollment.side_effect = IntegrityError(
        "INSERT", {}, Exception("fk")
    )

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_create_league_input(), CLUB)

    assert error.value.status_code == 400


@pytest.mark.parametrize("max_clubs", [21, 30])
async def test_create_league_max_clubs_over_limit(api, mocks, max_clubs):
    data = make_create_league_input()
    data.max_clubs = (
        max_clubs  # Pydantic lo acepta (le=30), el límite real lo pone el impl
    )

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_max_clubs_at_limit(api, mocks):
    data = make_create_league_input()
    data.max_clubs = 20

    result = await api.create_league(data, CLUB)

    assert result.max_clubs == 5  # lo que devuelve el repo mockeado
    mocks.league_repo.create_with_enrollment.assert_awaited_once()


async def test_get_league_public(api, mocks):

    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="LPF chiqui Mafia",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
        allows_draws=True,
        creator_club_id=CLUB.id,
    )

    club = SimpleNamespace(id=uuid.uuid4(), club_name="River Plate")
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = [club]

    result = await api.get_league(league.id)

    assert result.id == league.id
    assert result.name == "LPF chiqui Mafia"
    assert result.is_private is False
    assert result.status == "not_started"
    assert result.registered_clubs[0].club_name == "River Plate"
    assert result.creator_club_id == CLUB.id

    mocks.league_repo.get.assert_awaited_once_with(league.id)  # busco la liga


async def test_get_league_private(api, mocks):
    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="LPF chiqui Mafia",
        hashed_password="password",
        max_clubs=5,
        status="not_started",
        allows_draws=True,
        creator_club_id=CLUB.id,
    )
    club = SimpleNamespace(id=uuid.uuid4(), club_name="River Plate")
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = [club]

    result = await api.get_league(league.id)

    assert result.id == league.id
    assert result.name == "LPF chiqui Mafia"
    assert result.is_private is True
    assert result.status == "not_started"
    assert result.registered_clubs[0].club_name == "River Plate"


@pytest.mark.parametrize("status", ["started", "finished"])
async def test_get_league_not_available(api, mocks, status):
    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="LPF chiqui Mafia",
        hashed_password="password",
        max_clubs=5,
        status=status,
        allows_draws=True,
    )

    mocks.league_repo.get.return_value = league

    with (
        pytest.raises(HTTPException) as error
    ):  # basicamente digo, lo que viene tiene que ser una excepcion, y lo guardo en error
        await api.get_league(league.id)

    assert error.value.status_code == 404


# test listar ligas
async def test_list_leagues_public(api, mocks):
    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="Liga",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
        allows_draws=True,
        creator_club_id=CLUB.id,
    )
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
    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="Liga",
        hashed_password="hash",
        max_clubs=5,
        status="not_started",
        allows_draws=True,
        creator_club_id=CLUB.id,
    )
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

async def test_list_my_leagues(api, mocks):
    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="Liga",
        hashed_password=None,
        max_clubs=5,
        status="started",
    )
    clubs= [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())]
    mocks.league_repo.list_leagues_of_club.return_value = [league]
    mocks.league_repo.list_clubs_of_league.return_value = clubs
    
    result = await api.list_my_leagues(CLUB.id)

    assert len(result) == 1
    assert result[0].id == league.id
    assert result[0].max_clubs == 5
    assert result[0].status == "started"
    assert result[0].club_count == 2
    mocks.league_repo.list_leagues_of_club.assert_awaited_once_with(CLUB.id)

# tests de endpoint

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
                id=uuid.uuid4(),
                name=f"Jugador {i}",
                number=i + 1,
                power=100,
                agility=100,
                control=30,
                speed=30,
                strength=40,
                club_id=club.id,
            )
        )
    behaviors = []
    for i in range(3):
        behaviors.append(
            BehaviorDB(
                id=uuid.uuid4(),
                name=f"Comp {i}",
                code="def decide_action(): pass",
                club_id=club.id,
            )
        )
    session.add_all(players + behaviors)
    await session.commit()

    squad = []
    for i, player in enumerate(players):
        if i < 3:
            squad.append(
                {
                    "player_id": str(player.id),
                    "is_starter": True,
                    "behavior_id": str(behaviors[i].id),
                }
            )
        else:
            squad.append(
                {"player_id": str(player.id), "is_starter": False, "behavior_id": None}
            )
    return {
        "name": "Mi liga",
        "max_clubs": 5,
        "match_duration_minutes": 10,
        "formation": "TRIANGLE",
        "players": squad,
    }


async def add_league(session, club, name, status, password=None):
    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name=name,
            hashed_password=password,
            max_clubs=5,
            match_duration_minutes=10,
            status=status,
            creator_club_id=club.id,
        )
    )
    await session.commit()  # primero la liga, después la inscripción (clave foránea)
    session.add(
        LeagueEnrollmentDB(id=uuid.uuid4(), league_id=league_id, club_id=club.id)
    )
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
    assert data["allows_draws"] is True  # sin el campo, admite empates
    assert data["registered_clubs"][0]["club_name"] == "Instituto"
    assert await count_leagues(session) == 1
    inscripciones = await session.scalar(
        select(func.count()).select_from(LeagueEnrollmentDB)
    )
    jugadores = await session.scalar(
        select(func.count()).select_from(LeagueEnrollmentPlayerDB)
    )
    assert inscripciones == 1  # el creador queda inscripto
    assert jugadores == 6


async def test_endpoint_create_league_without_draws(client, session, club):
    body = await make_body(session, club)
    body["allows_draws"] = False

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 201
    assert r.json()["allows_draws"] is False


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


async def test_endpoint_create_league_without_formation(client, session, club):
    body = await make_body(session, club)
    del body["formation"]

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert await count_leagues(session) == 0


async def test_endpoint_create_league_unknown_formation(client, session, club):
    body = await make_body(session, club)
    body["formation"] = "DIAGONAL"  # no está en el contrato

    r = await client.post(URL, json=body, headers=auth_header(club))

    assert r.status_code == 400
    assert "formation" in r.json()["message"]
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
    session.add(
        UserDB(id=other_user_id, email="otro@prueba.com", hashed_password="hash")
    )
    await session.flush()
    session.add(
        ClubDB(
            id=other_club_id,
            club_name="Otro club",
            avatar_url="https://img.com/avatar.png",
            user_id=other_user_id,
        )
    )
    await session.commit()
    session.add(
        BehaviorDB(
            id=other_behavior_id,
            name="Ajeno",
            code="def decide_action(): pass",
            club_id=other_club_id,
        )
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

# --- GET /club/leagues (ligas de mi club) ---
MY_LEAGUES_URL = "/club/leagues"

async def test_endpoint_list_my_leagues_returns_200(client, session, club):
    await add_league(session, club, "Liga no iniciada", "not_started")
    await add_league(session, club, "Liga iniciada", "started")
    await add_league(session, club, "Liga cancelada", "cancelled")

    r = await client.get(MY_LEAGUES_URL, headers=auth_header(club))

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for league in data:
        assert league["status"] != "cancelled"
        assert league["club_count"] == 1

async def test_endpoint_list_my_leagues_not_enrolled(client, session, club):
    # liga creada por otro club, en la que mi club no está inscripto
    other_user_id = uuid.uuid4()
    other_club = SimpleNamespace(id=uuid.uuid4(), user_id=other_user_id)
    session.add(UserDB(id=other_user_id, email="otro@prueba.com", hashed_password="hash"))
    await session.flush()
    session.add(
        ClubDB(
            id=other_club.id,
            club_name="River Plate",
            avatar_url="https://img.com/avatar.png",
            user_id=other_user_id,
        )
    )
    await session.commit()
    await add_league(session, other_club, "Liga ajena", "started")

    r = await client.get(MY_LEAGUES_URL, headers=auth_header(club))

    assert r.status_code == 200
    assert r.json() == []

async def test_endpoint_list_my_leagues_without_token_returns_401(client, session):
    r = await client.get(MY_LEAGUES_URL)

    assert r.status_code == 401
    assert "message" in r.json()

async def test_join_league_public_endpoint(api, mocks):
    # configuramos la liga que vamos a obtener
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="LPF chiqui Mafia",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = []  # simulamos 0 clubes inscriptos

    # llamada al endpoint
    await api.join_league(league_id, make_join_league_input(), CLUB)

    # verificamos que se haya intentado añadir la inscripcion
    mocks.league_repo.add_enrollment.assert_awaited_once()


async def test_join_league_saves_formation(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, name="Liga", hashed_password=None, max_clubs=5, status="not_started"
    )
    mocks.league_repo.list_clubs_of_league.return_value = []
    data = make_join_league_input()
    data.formation = "OFFENSIVE_LINE"

    await api.join_league(league_id, data, CLUB)

    assert mocks.league_repo.add_enrollment.await_args.kwargs["formation"] == "OFFENSIVE_LINE"


async def test_join_league_private_wrong_password(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="LPF chiqui Mafia",
        hashed_password="hashed_pw",
        max_clubs=5,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league
    mocks.verify_password.return_value = False

    with pytest.raises(HTTPException) as error:
        await api.join_league(
            league_id, make_join_league_input(password="wrong_pw"), CLUB
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Contraseña incorrecta"

    mocks.verify_password.assert_awaited_once_with("wrong_pw", "hashed_pw")
    mocks.league_repo.add_enrollment.assert_not_awaited()


async def test_join_league_full_capacity(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="Liga Llena",
        hashed_password=None,
        max_clubs=3,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league
    # simulamos que esta llena
    mocks.league_repo.list_clubs_of_league.return_value = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    with pytest.raises(HTTPException) as error:
        await api.join_league(league_id, make_join_league_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.add_enrollment.assert_not_awaited()


async def test_join_league_already_enrolled(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="Liga",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = []

    # configuramos el mock para que tire la excepcion de ClubAlreadyEnrolled
    mocks.league_repo.add_enrollment.side_effect = ClubAlreadyEnrolled(CLUB.id)

    with pytest.raises(HTTPException) as error:
        await api.join_league(league_id, make_join_league_input(), CLUB)

    assert error.value.status_code == 409


async def test_club_registered_event(api, mocks):
    # configuramos la liga
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="LPF chiqui Mafia",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league
    # simulamos que ya hay un club inscripto
    mocks.league_repo.list_clubs_of_league.return_value = [MagicMock()]

    # llamamos al endpoint
    await api.join_league(league_id, make_join_league_input(), CLUB)

    # verificamos que impacto en la db
    mocks.league_repo.add_enrollment.assert_awaited_once()

    # VERIFICAMOS EL EVENTO WEBSOCKET
    # armamos el evento que esperamos recibir luego de una inscripcion exitosa
    expected_event = {
        "type": "clubRegistered",
        "data": {
            "league_id": str(league_id),
            "club_id": str(CLUB.id),
            "club_name": CLUB.club_name,
            "registered_count": 2,
        },
    }

    # le preguntamos al mock si el endpoint llamo a broadcast con esos datos
    mocks.lobby_connection.broadcast.assert_awaited_once_with(league_id, expected_event)


async def test_leave_league_success(api, mocks):
    # configuramos la liga
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="LPF chiqui Mafia",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league

    # simulamos que después de borrar quedan 0 clubes
    mocks.league_repo.list_clubs_of_league.return_value = []

    # simulamos que remove_enrollment no arroja error (exito)
    mocks.league_repo.remove_enrollment = AsyncMock()

    # llamamos al endpoint
    await api.leave_league(league_id, CLUB)

    # verificamos que se haya intentado eliminar de la db
    mocks.league_repo.remove_enrollment.assert_awaited_once_with(league_id, CLUB.id)

    # VERIFICAMOS EL EVENTO WEBSOCKET
    # armamos el evento que esperamos recibir luego de que alguien se de de baja a la liga
    expected_event = {
        "type": "clubLeft",
        "data": {
            "league_id": str(league_id),
            "club_id": str(CLUB.id),
            "registered_count": 0,
        },
    }
    mocks.lobby_connection.broadcast.assert_awaited_once_with(league_id, expected_event)


async def test_leave_league_not_found(api, mocks):
    league_id = uuid.uuid4()
    # simulamos que el repo no encontro la liga (o sea, retorna None)
    mocks.league_repo.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.leave_league(league_id, CLUB)

    assert error.value.status_code == 404
    assert error.value.detail == "La liga indicada no existe"

    # verificamos que nunca intento borrar nada ni enviar el evento
    mocks.league_repo.remove_enrollment.assert_not_awaited()
    mocks.lobby_connection.broadcast.assert_not_awaited()


async def test_leave_league_already_started(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="Liga Iniciada",
        hashed_password=None,
        max_clubs=5,
        status="started",  # no se puede abandora una liga iniciada
    )
    mocks.league_repo.get.return_value = league

    with pytest.raises(HTTPException) as error:
        await api.leave_league(league_id, CLUB)

    # comprobamos las respuestas de error esperadas
    assert error.value.status_code == 409
    assert error.value.detail == "La liga ya se encuentra iniciada"
    # verificamos que no se ejecuto el metodo del repo
    mocks.league_repo.remove_enrollment.assert_not_awaited()


async def test_leave_league_not_enrolled(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="Liga",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
    )
    mocks.league_repo.get.return_value = league

    # forzamos que el metodo de borrar falle porque el club no estaba inscripto 
    mocks.league_repo.remove_enrollment = AsyncMock(side_effect=ClubNotEnrolled())

    with pytest.raises(HTTPException) as error:
        await api.leave_league(league_id, CLUB)

    # comprobamos las respuestas de error esperadas
    assert error.value.status_code == 404
    assert error.value.detail == "El club no está inscripto en esta liga"
    # verificamos que no se emitio ningun evento
    mocks.lobby_connection.broadcast.assert_not_awaited()


async def test_start_league_success(api, mocks):
    # configuramos la liga
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="Liga Lista Para Empezar",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
        allows_draws=True,
        creator_club_id=CLUB.id,  #el club que llama es el creador
    )
    mocks.league_repo.get.return_value = league

    club2 = SimpleNamespace(id=uuid.uuid4(), club_name="Boca")
    club3 = SimpleNamespace(id=uuid.uuid4(), club_name="Racing")
    # simulamos que hay 3 clubes inscriptos (el minimo)
    mocks.league_repo.list_clubs_of_league.return_value = [CLUB, club2, club3]

    # simulamos que start_league no lanza errores
    mocks.league_repo.start_league = AsyncMock()

    # llamamos al endpoint
    result = await api.start_league(league_id, CLUB)

    # verificamos que se llamo al repositorio para iniciarla
    mocks.league_repo.start_league.assert_awaited_once_with(league_id)

    # verificamos que se emitio el evento ws leagueStarted
    expected_event = {
        "type": "leagueStarted",
        "data": {"league_id": str(league_id)},
    }
    mocks.lobby_connection.broadcast.assert_awaited_once_with(league_id, expected_event)
    mocks.league_scheduler.schedule.assert_called_once_with(league_id)

    # verificamos que el LeagueDetail devuelto tenga el estado en "started"
    assert result.status == "started"
    assert result.id == league_id


async def test_start_league_not_found(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.start_league(league_id, CLUB)

    assert error.value.status_code == 404
    assert error.value.detail == "La liga indicada no existe"
    mocks.league_repo.start_league.assert_not_awaited()


async def test_start_league_not_creator(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        status="not_started",
        creator_club_id=uuid.uuid4(),  # un ID distinto al del club que hace la llamada
    )
    mocks.league_repo.get.return_value = league

    with pytest.raises(HTTPException) as error:
        await api.start_league(league_id, CLUB)

    assert error.value.status_code == 403
    assert error.value.detail == "Solo el creador de la liga puede iniciarla"
    mocks.league_repo.start_league.assert_not_awaited()


async def test_start_league_already_started(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        status="started",  # ya esta iniciada
        creator_club_id=CLUB.id,
    )
    mocks.league_repo.get.return_value = league

    with pytest.raises(HTTPException) as error:
        await api.start_league(league_id, CLUB)

    assert error.value.status_code == 409
    mocks.league_repo.start_league.assert_not_awaited()


async def test_start_league_not_enough_clubs(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id, status="not_started", creator_club_id=CLUB.id
    )
    mocks.league_repo.get.return_value = league

    # solo hay 2 clubs inscriptos
    mocks.league_repo.list_clubs_of_league.return_value = [CLUB, MagicMock()]

    with pytest.raises(HTTPException) as error:
        await api.start_league(league_id, CLUB)

    assert error.value.status_code == 400
    assert error.value.detail == "No hay suficientes clubes inscriptos para iniciar la liga"
    mocks.league_repo.start_league.assert_not_awaited()


async def test_start_league_repo_failure_returns_500(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        name="Liga Test",
        hashed_password=None,
        max_clubs=5,
        status="not_started",
        creator_club_id=CLUB.id,
    )
    mocks.league_repo.get.return_value = league
    mocks.league_repo.list_clubs_of_league.return_value = [
        CLUB,
        MagicMock(),
        MagicMock(),
    ]

    # simulamos un fallo critico en la base de datos (por ej. un IntegrityError producido por una race condition)
    # esto es el error no documentado (500) que atajamos en el repo
    mocks.league_repo.start_league.side_effect = LeagueStartFailure()

    with pytest.raises(HTTPException) as error:
        await api.start_league(league_id, CLUB)

    # verificamos que atajo nuestra excepcion y devolvio el error 500
    assert error.value.status_code == 500

    # verificamos que si falla la base de datos, NUNCA se emite el evento ws
    mocks.lobby_connection.broadcast.assert_not_awaited()
    mocks.league_scheduler.schedule.assert_not_called()


# endpoint tabla de posiciones
@pytest.mark.parametrize("status", ["started", "finished"])
async def test_get_standings_success(api, mocks, status):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, status=status
    )
    club1_id = uuid.uuid4()
    club2_id = uuid.uuid4()
    mocks.league_repo.get_standings.return_value = [
        (
            SimpleNamespace(
                club_id=club1_id,
                points=6,
                rank=1,
                matches_played=2,
                won=2,
                drawn=0,
                lost=0,
                goals_for=5,
                goals_against=1,
                goals_dif=4,
            ),
            "River Plate",
        ),
        (
            SimpleNamespace(
                club_id=club2_id,
                points=0,
                rank=2,
                matches_played=2,
                won=0,
                drawn=0,
                lost=2,
                goals_for=1,
                goals_against=5,
                goals_dif=-4,
            ),
            "Boca Juniors",
        ),
    ]

    result = await api.get_standings(league_id)

    mocks.league_repo.get.assert_awaited_once_with(league_id)
    mocks.league_repo.get_standings.assert_awaited_once_with(league_id)
    assert len(result) == 2
    assert result[0].club_id == club1_id
    assert result[0].club_name == "River Plate"
    assert result[0].points == 6
    assert result[0].rank == 1
    assert result[0].matches_played == 2
    assert result[0].won == 2
    assert result[0].drawn == 0
    assert result[0].lost == 0
    assert result[0].goals_for == 5
    assert result[0].goals_against == 1
    assert result[0].goals_dif == 4
    assert result[1].club_id == club2_id
    assert result[1].club_name == "Boca Juniors"
    assert result[1].rank == 2


async def test_get_standings_league_not_found(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.get_standings(league_id)

    assert error.value.status_code == 404
    mocks.league_repo.get_standings.assert_not_awaited()


@pytest.mark.parametrize("status", ["not_started", "cancelled"])
async def test_get_standings_league_not_started_returns_409(api, mocks, status):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, status=status
    )

    with pytest.raises(HTTPException) as error:
        await api.get_standings(league_id)

    assert error.value.status_code == 409
    mocks.league_repo.get_standings.assert_not_awaited()


# chequeamos tambien que el endpoint los mande ordenados (el repo ya lo hace, el endpoint
# solo deberia mapear al modelo y devolver la lista)
async def test_endpoint_get_standings_returns_200_ordered(client, session, club):
    league_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    other_club_id = uuid.uuid4()
    session.add(
        UserDB(id=other_user_id, email="rival@prueba.com", hashed_password="hash")
    )
    await session.flush()
    session.add(
        ClubDB(
            id=other_club_id,
            club_name="Belgrano",
            avatar_url="https://img.com/b.png",
            user_id=other_user_id,
        )
    )
    session.add(
        LeagueDB(
            id=league_id,
            name="Liga En Curso",
            max_clubs=5,
            match_duration_minutes=10,
            status="started",
            creator_club_id=club.id,
        )
    )
    await session.flush()
    session.add_all(
        [
            LeagueStandingsDB(
                league_id=league_id,
                club_id=club.id,
                rank=2,
                points=1,
                matches_played=1,
                won=0,
                drawn=1,
                lost=0,
                goals_for=1,
                goals_against=1,
                goals_dif=0,
            ),
            LeagueStandingsDB(
                league_id=league_id,
                club_id=other_club_id,
                rank=1,
                points=3,
                matches_played=1,
                won=1,
                drawn=0,
                lost=0,
                goals_for=2,
                goals_against=0,
                goals_dif=2,
            ),
        ]
    )
    await session.commit()

    r = await client.get(
        f"{URL}/{league_id}/standings", headers=auth_header(club)
    )

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["club_id"] == str(other_club_id)
    assert data[0]["club_name"] == "Belgrano"
    assert data[0]["points"] == 3
    assert data[0]["rank"] == 1
    assert data[0]["goals_dif"] == 2
    assert data[1]["club_id"] == str(club.id)
    assert data[1]["club_name"] == "Instituto"
    assert data[1]["points"] == 1
    assert data[1]["rank"] == 2


async def test_endpoint_get_standings_not_found_returns_404(client, club):
    r = await client.get(
        f"{URL}/{uuid.uuid4()}/standings", headers=auth_header(club)
    )

    assert r.status_code == 404
    assert "message" in r.json()


async def test_endpoint_get_standings_not_started_returns_409(
    client, session, club
):
    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name="Liga Sin Iniciar",
            max_clubs=5,
            match_duration_minutes=10,
            status="not_started",
            creator_club_id=club.id,
        )
    )
    await session.commit()

    r = await client.get(
        f"{URL}/{league_id}/standings", headers=auth_header(club)
    )

    assert r.status_code == 409
    assert "message" in r.json()


# --- GET y PUT /leagues/{league_id}/lineup ---


def make_enrolled_players():
    # los 6 convocados del club: los 3 primeros titulares con comportamiento
    return [
        SimpleNamespace(
            player_id=uuid.uuid4(),
            is_starter=i < 3,
            behavior_id=uuid.uuid4() if i < 3 else None,
        )
        for i in range(6)
    ]


def make_lineup_input(players, formation="OFFENSIVE_LINE"):
    return SubmitLineupInput(
        formation=formation,
        players=[
            SquadPlayerInput(
                player_id=p.player_id,
                is_starter=p.is_starter,
                behavior_id=p.behavior_id,
            )
            for p in players
        ],
    )


def mock_lineup(mocks, players, status="started"):
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=uuid.uuid4(), status=status
    )
    mocks.league_repo.get_enrollment.return_value = SimpleNamespace(
        id=uuid.uuid4(), formation="TRIANGLE"
    )
    mocks.league_repo.list_enrollment_players.return_value = players
    # comportamiento del club y de jugador
    mocks.session.get = AsyncMock(
        return_value=SimpleNamespace(club_id=CLUB.id, kind="player")
    )


async def test_get_league_lineup_success(api, mocks):
    mock_lineup(mocks, make_enrolled_players())

    result = await api.get_league_lineup(uuid.uuid4(), CLUB)

    assert result.formation == "TRIANGLE"
    assert len(result.players) == 6


async def test_update_league_lineup_success(api, mocks):
    players = make_enrolled_players()
    mock_lineup(mocks, players)

    await api.update_league_lineup(uuid.uuid4(), make_lineup_input(players), CLUB)

    mocks.league_repo.update_lineup.assert_awaited_once()


@pytest.mark.parametrize("status", ["finished", "cancelled"])
async def test_update_league_lineup_returns_409(api, mocks, status):
    players = make_enrolled_players()
    mock_lineup(mocks, players, status=status)

    with pytest.raises(HTTPException) as error:
        await api.update_league_lineup(uuid.uuid4(), make_lineup_input(players), CLUB)

    assert error.value.status_code == 409


# comportamiento que no existe, de otro club o de DT
@pytest.mark.parametrize(
    "behavior",
    [
        None,
        SimpleNamespace(club_id=uuid.uuid4(), kind="player"),
        SimpleNamespace(club_id=CLUB.id, kind="coach"),
    ],
)
async def test_update_league_lineup_invalid_behavior_returns_400(api, mocks, behavior):
    players = make_enrolled_players()
    mock_lineup(mocks, players)
    mocks.session.get = AsyncMock(return_value=behavior)

    with pytest.raises(HTTPException) as error:
        await api.update_league_lineup(uuid.uuid4(), make_lineup_input(players), CLUB)

    assert error.value.status_code == 400

async def test_update_league_lineup_player_not_enrolled_returns_400(api, mocks):
    players = make_enrolled_players()
    mock_lineup(mocks, players)
    # mandamos un suplente que no es convocado (lista nueva, no tocamos la del mock)
    other = SimpleNamespace(player_id=uuid.uuid4(), is_starter=False, behavior_id=None)
    sent = players[:5] + [other]

    with pytest.raises(HTTPException) as error:
        await api.update_league_lineup(uuid.uuid4(), make_lineup_input(sent), CLUB)

    assert error.value.status_code == 400


@pytest.mark.parametrize("league_status", ["started", "finished"])
async def test_list_league_matches_success(api, mocks, league_status):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, status=league_status
    )
    match_id = uuid.uuid4()
    home_id = uuid.uuid4()
    away_id = uuid.uuid4()
    mocks.match_repo.list_by_league.return_value = [
        SimpleNamespace(
            id=match_id,
            league_id=league_id,
            round_number=1,
            home_club_id=home_id,
            home_club=SimpleNamespace(club_name="River Plate"),
            away_club_id=away_id,
            away_club=SimpleNamespace(club_name="Boca Juniors"),
            status=MatchStatus.finished,
            home_score=2,
            away_score=1,
            home_penalties=None,
            away_penalties=None,
        )
    ]

    result = await api.list_league_matches(league_id, None)

    mocks.league_repo.get.assert_awaited_once_with(league_id)
    mocks.match_repo.list_by_league.assert_awaited_once_with(
        league_id, status=None
    )
    assert len(result) == 1
    assert result[0].id == match_id
    assert result[0].league_id == league_id
    assert result[0].round_number == 1
    assert result[0].home_club_id == home_id
    assert result[0].home_club_name == "River Plate"
    assert result[0].away_club_id == away_id
    assert result[0].away_club_name == "Boca Juniors"
    assert result[0].status == "finished"
    assert result[0].home_score == 2
    assert result[0].away_score == 1


async def test_list_league_matches_with_status_filter(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, status="started"
    )
    mocks.match_repo.list_by_league.return_value = []

    result = await api.list_league_matches(league_id, "scheduled")

    assert result == []
    mocks.match_repo.list_by_league.assert_awaited_once_with(
        league_id, status=MatchStatus.scheduled
    )


async def test_list_league_matches_invalid_status_returns_400(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, status="started"
    )

    with pytest.raises(HTTPException) as error:
        await api.list_league_matches(league_id, "estado_invalido")

    assert error.value.status_code == 400
    mocks.match_repo.list_by_league.assert_not_awaited()


async def test_list_league_matches_not_found_returns_404(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.list_league_matches(league_id, None)

    assert error.value.status_code == 404
    mocks.match_repo.list_by_league.assert_not_awaited()


@pytest.mark.parametrize("league_status", ["not_started", "cancelled"])
async def test_list_league_matches_not_started_returns_409(
    api, mocks, league_status
):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = SimpleNamespace(
        id=league_id, status=league_status
    )

    with pytest.raises(HTTPException) as error:
        await api.list_league_matches(league_id, None)

    assert error.value.status_code == 409
    mocks.match_repo.list_by_league.assert_not_awaited()


async def test_endpoint_list_league_matches_returns_200_ordered_and_filtered(
    client, session, club
):
    league_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    other_club_id = uuid.uuid4()
    session.add(
        UserDB(id=other_user_id, email="rival@prueba.com", hashed_password="hash")
    )
    await session.flush()
    session.add(
        ClubDB(
            id=other_club_id,
            club_name="Belgrano",
            avatar_url="https://img.com/b.png",
            user_id=other_user_id,
        )
    )
    session.add(
        LeagueDB(
            id=league_id,
            name="Liga En Curso",
            max_clubs=5,
            match_duration_minutes=10,
            status="started",
            creator_club_id=club.id,
        )
    )
    await session.flush()

    m_round_2 = MatchDB(
        id=uuid.uuid4(),
        league_id=league_id,
        round_number=2,
        home_club_id=club.id,
        away_club_id=other_club_id,
        status=MatchStatus.scheduled,
    )
    m_round_1 = MatchDB(
        id=uuid.uuid4(),
        league_id=league_id,
        round_number=1,
        home_club_id=other_club_id,
        away_club_id=club.id,
        status=MatchStatus.finished,
        home_score=3,
        away_score=1,
    )
    session.add_all([m_round_2, m_round_1])
    await session.commit()

    # sin filtro: devuelve ambos ordenados por round_number
    r = await client.get(
        f"{URL}/{league_id}/matches", headers=auth_header(club)
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["id"] == str(m_round_1.id)
    assert data[0]["league_id"] == str(league_id)
    assert data[0]["round_number"] == 1
    assert data[0]["home_club_id"] == str(other_club_id)
    assert data[0]["home_club_name"] == "Belgrano"
    assert data[0]["away_club_id"] == str(club.id)
    assert data[0]["away_club_name"] == "Instituto"
    assert data[0]["status"] == "finished"
    assert data[0]["home_score"] == 3
    assert data[0]["away_score"] == 1
    assert data[1]["id"] == str(m_round_2.id)
    assert data[1]["round_number"] == 2
    assert data[1]["status"] == "scheduled"

    # con filtro status=scheduled
    r_filtered = await client.get(
        f"{URL}/{league_id}/matches?status=scheduled", headers=auth_header(club)
    )
    assert r_filtered.status_code == 200
    filtered_data = r_filtered.json()
    assert len(filtered_data) == 1
    assert filtered_data[0]["id"] == str(m_round_2.id)


async def test_endpoint_list_league_matches_not_found_returns_404(client, club):
    r = await client.get(
        f"{URL}/{uuid.uuid4()}/matches", headers=auth_header(club)
    )
    assert r.status_code == 404
    assert "message" in r.json()


async def test_endpoint_list_league_matches_not_started_returns_409(
    client, session, club
):
    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name="Liga Sin Iniciar",
            max_clubs=5,
            match_duration_minutes=10,
            status="not_started",
            creator_club_id=club.id,
        )
    )
    await session.commit()

    r = await client.get(
        f"{URL}/{league_id}/matches", headers=auth_header(club)
    )
    assert r.status_code == 409
    assert "message" in r.json()


async def test_cancel_league_success(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id, status="not_started", creator_club_id=CLUB.id
    )
    mocks.league_repo.get.return_value = league

    await api.cancel_league(league_id, CLUB)

    # verificamos que se cancelo la liga
    mocks.league_repo.cancel_league.assert_awaited_once_with(league_id)

    # verificamos que se emitio el evento y se cerro el canal
    expected_event = {
        "type": "leagueCancelled",
        "data": {"league_id": str(league_id)},
    }
    mocks.lobby_connection.broadcast.assert_awaited_once_with(league_id, expected_event)
    mocks.lobby_connection.close_all.assert_awaited_once_with(league_id)


async def test_cancel_league_not_found(api, mocks):
    league_id = uuid.uuid4()
    mocks.league_repo.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.cancel_league(league_id, CLUB)

    assert error.value.status_code == 404
    mocks.league_repo.cancel_league.assert_not_awaited()
    mocks.lobby_connection.broadcast.assert_not_awaited()


async def test_cancel_league_not_creator(api, mocks):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id,
        status="not_started",
        creator_club_id=uuid.uuid4(),  # un ID distinto al del club que hace la llamada
    )
    mocks.league_repo.get.return_value = league

    with pytest.raises(HTTPException) as error:
        await api.cancel_league(league_id, CLUB)

    assert error.value.status_code == 403
    assert error.value.detail == "Solo el creador de la liga puede cancelarla"
    mocks.league_repo.cancel_league.assert_not_awaited()


@pytest.mark.parametrize("league_status", ["started", "finished", "cancelled"])
async def test_cancel_league_not_cancellable(api, mocks, league_status):
    league_id = uuid.uuid4()
    league = SimpleNamespace(
        id=league_id, status=league_status, creator_club_id=CLUB.id
    )
    mocks.league_repo.get.return_value = league

    with pytest.raises(HTTPException) as error:
        await api.cancel_league(league_id, CLUB)

    assert error.value.status_code == 409
    mocks.league_repo.cancel_league.assert_not_awaited()
