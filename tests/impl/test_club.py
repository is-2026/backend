import uuid

import pytest
from sqlalchemy import func, select
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.security.tokens import create_access_token
from app.models.change_coach_input import ChangeCoachInput
from app.impl.club_api_impl import ClubApiImpl
from app.impl.behavior_api_impl import BehaviorApiImpl
from app.db.league import LeagueDB
from app.db.standings import LeagueStandingsDB

CLUB_NAME = "Instituto"
AVATAR_URL = "https://img.com/avatar.png"
URL = "/club"
VALID = {"club_name": CLUB_NAME, "avatar_url": AVATAR_URL}


# para contar filas: una fila -> una UserDB (por e.j)
async def _count_model(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


@pytest.fixture
async def user(session):
    """Crea un usuario real en la base de datos de test y lo devuelve."""
    u = UserDB(email="hola@prueba.com", hashed_password="hash")
    session.add(u)
    await session.commit()
    return u


def auth_header(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def test_valid_create_club_returns_201_and_club(client, session, user):
    r = await client.post(url=URL, json=VALID, headers=auth_header(user))

    assert r.status_code == 201
    body = r.json()
    uuid.UUID(body["id"])  # ver si es uuid
    assert body["club_name"] == CLUB_NAME
    assert body["avatar_url"] == AVATAR_URL
    assert body["user_id"] == str(user.id)
    assert await _count_model(session, ClubDB) == 1
    assert await _count_model(session, BehaviorDB) == len(DEFAULT_BEHAVIORS)  # son 3


@pytest.mark.parametrize(
    "body",
    [
        {"club_name": CLUB_NAME, "avatar_url": "estonoesunaurl"},
        {"club_name": "           ", "avatar_url": AVATAR_URL},
        {"club_name": "x" * 51, "avatar_url": AVATAR_URL},
        {"avatar_url": AVATAR_URL},
        {"club_name": CLUB_NAME},
        {},
    ],
    ids=[
        "invalid_url",
        "blank_club_name",
        "long_club_name",
        "missing_club_name",
        "missing_avatar_url",
        "empty",
    ],
)
async def test_missing_or_invalid_field_returns_400_club(client, session, user, body):
    r = await client.post(URL, json=body, headers=auth_header(user))

    assert r.status_code == 400
    assert "message" in r.json()
    assert await _count_model(session, ClubDB) == 0


async def test_only_one_club_per_user(client, session, user):
    r1 = await client.post(URL, json=VALID, headers=auth_header(user))
    r2 = await client.post(URL, json=VALID, headers=auth_header(user))

    assert r1.status_code == 201
    assert r2.status_code == 409
    assert "message" in r2.json()
    assert await _count_model(session, ClubDB) == 1


async def test_create_club_without_token_returns_401(client, session):
    r = await client.post(URL, json=VALID)

    assert r.status_code == 401
    assert "message" in r.json()
    assert await _count_model(session, ClubDB) == 0

@patch("app.impl.club_api_impl.BehaviorRepository")
@patch("app.impl.club_api_impl.ClubRepository")
async def test_change_coach_succes(mocked_club_repo_class, mocked_behavior_repo_class):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Gallardo",
        code="def decide_coach():\n    pass",
        club_id=club_id,
        kind="coach",
    )
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=uuid.uuid4(),
        coach_behavior_id=behavior_id,
    )
    change_input= ChangeCoachInput(
        behavior_id= behavior_id
    )
    mocked_behavior_repo = MagicMock()
    mocked_behavior_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_behavior_repo_class.return_value = mocked_behavior_repo

    mocked_club_repo = MagicMock()
    mocked_club_repo.update_coach = AsyncMock(return_value= club_db)
    mocked_club_repo_class.return_value = mocked_club_repo

    result = await ClubApiImpl(MagicMock()).change_coach(change_input, club_id)

    mocked_behavior_repo.get_id_and_club.assert_awaited_once_with(behavior_id, club_id)
    mocked_club_repo.update_coach.assert_awaited_once_with(club_id, behavior_id)
    assert result.id == club_id
    assert result.coach_behavior_id == behavior_id

@patch("app.impl.club_api_impl.BehaviorRepository")
@patch("app.impl.club_api_impl.ClubRepository")
async def test_change_coach_quit_DT(mocked_club_repo_class, mocked_behavior_repo_class):
    club_id = uuid.uuid4()
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=uuid.uuid4(),
        coach_behavior_id=None,
    )
    change_input= ChangeCoachInput(
        behavior_id= None
    )
    mocked_behavior_repo = MagicMock()
    mocked_behavior_repo.get_id_and_club = AsyncMock()
    mocked_behavior_repo_class.return_value = mocked_behavior_repo

    mocked_club_repo = MagicMock()
    mocked_club_repo.update_coach = AsyncMock(return_value= club_db)
    mocked_club_repo_class.return_value = mocked_club_repo

    result = await ClubApiImpl(MagicMock()).change_coach(change_input, club_id)

    mocked_behavior_repo.get_id_and_club.assert_not_awaited()
    mocked_club_repo.update_coach.assert_awaited_once_with(club_id, None)
    assert result.id == club_id
    assert result.coach_behavior_id is None

@patch("app.impl.club_api_impl.BehaviorRepository")
@patch("app.impl.club_api_impl.ClubRepository")
async def test_change_coach_not_behavior(mocked_club_repo_class, mocked_behavior_repo_class):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    change_input= ChangeCoachInput(
        behavior_id= behavior_id
    )
    mocked_behavior_repo = MagicMock()
    mocked_behavior_repo.get_id_and_club = AsyncMock(return_value= None)
    mocked_behavior_repo_class.return_value = mocked_behavior_repo

    mocked_club_repo = MagicMock()
    mocked_club_repo.update_coach = AsyncMock()
    mocked_club_repo_class.return_value = mocked_club_repo
    with pytest.raises(HTTPException) as exc_info:
        await ClubApiImpl(MagicMock()).change_coach(change_input, club_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "El comportamiento no existe"

@patch("app.impl.club_api_impl.BehaviorRepository")
@patch("app.impl.club_api_impl.ClubRepository")
async def test_change_coach_behavior_player(mocked_club_repo_class, mocked_behavior_repo_class):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Gallardo Jugador",
        code="def decide_action():\n    pass",
        club_id=club_id,
        kind="player",
    )
    club_db = ClubDB(
        id=club_id,
        club_name="Club de Prueba",
        avatar_url="https://example.com/avatar.png",
        user_id=uuid.uuid4(),
        coach_behavior_id=behavior_id,
    )
    change_input= ChangeCoachInput(
        behavior_id= behavior_id
    )
    mocked_behavior_repo = MagicMock()
    mocked_behavior_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_behavior_repo_class.return_value = mocked_behavior_repo

    mocked_club_repo = MagicMock()
    mocked_club_repo.update_coach = AsyncMock(return_value= club_db)
    mocked_club_repo_class.return_value = mocked_club_repo
    with pytest.raises(HTTPException) as exc_info:
        await ClubApiImpl(MagicMock()).change_coach(change_input, club_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "El comportamiento es de jugador"
    
# creacion de club con POST /club y lo obtenemos con GET /club:
# deberia devolver los datos del club de ese usuario
async def test_get_my_club_returns_200(client, user):
    await client.post(URL, json=VALID, headers=auth_header(user))

    res = await client.get(URL, headers=auth_header(user))

    assert res.status_code == 200
    body = res.json()
    assert body["club_name"] == CLUB_NAME
    assert body["avatar_url"] == AVATAR_URL
    assert body["user_id"] == str(user.id)


# el usuario todavia no creo su club: tiene que responder 404
async def test_get_my_club_without_club_returns_404(client, user):
    res = await client.get(URL, headers=auth_header(user))
    assert res.status_code == 404
    assert res.json()["message"] == "El usuario no tiene un club creado"


# pedimos GET /club sin token: tiene que responder 401
async def test_get_my_club_without_token_returns_401(client):
    res = await client.get(URL)
    assert res.status_code == 401
    assert "No autorizado" in res.json()["message"]

# pedimos el perfil de un club sin token: debe responder 401
async def test_get_club_profile_without_token_returns_401(client):
    res = await client.get(f"/clubs/{uuid.uuid4()}")
    assert res.status_code == 401
    assert "No autorizado" in res.json()["message"]


# pedimos el perfil de un club que no existe: debe responder 404
async def test_get_club_profile_not_found_returns_404(client, user):
    res = await client.get(f"/clubs/{uuid.uuid4()}", headers=auth_header(user))
    assert res.status_code == 404
    assert res.json()["message"] == "El club no existe"


# prueba de club que no jugo en ninguna liga publica:
# debe tener todos los campos en 0 y sin posicion en el ranking
async def test_get_club_profile_without_matches(client, session, user):
    club_id = uuid.uuid4()
    session.add(ClubDB(id=club_id, club_name=CLUB_NAME, avatar_url=AVATAR_URL, user_id=user.id))
    await session.commit()

    res = await client.get(f"/clubs/{club_id}", headers=auth_header(user))

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(club_id)
    assert body["club_name"] == CLUB_NAME
    assert body["ranking_position"] is None
    assert body["points"] == 0
    assert body["matches_played"] == 0


# creamos dos clubes en una liga publica y el nuestro queda segundo:
# el perfil tiene que traer la misma posicion y los mismos numeros que /ranking
async def test_get_club_profile_matches_ranking(client, session, user):
    other_user_id, club_id, other_id, league_id = (uuid.uuid4() for _ in range(4))
    session.add(UserDB(id=other_user_id, email="otro@prueba.com", hashed_password="hash"))
    await session.flush()
    session.add_all([
        ClubDB(id=club_id, club_name=CLUB_NAME, avatar_url=AVATAR_URL, user_id=user.id),
        ClubDB(id=other_id, club_name="Talleres", avatar_url=AVATAR_URL, user_id=other_user_id),
    ])
    await session.flush()
    session.add(LeagueDB(id=league_id, name="Liga", hashed_password=None, max_clubs=5,
                         match_duration_minutes=10, status="started", creator_club_id=club_id))
    await session.flush()
    session.add_all([
        LeagueStandingsDB(league_id=league_id, club_id=other_id, rank=1, points=6,
                          matches_played=2, won=2, won_penalties=0, drawn=0, lost=0,
                          goals_for=4, goals_against=1),
        LeagueStandingsDB(league_id=league_id, club_id=club_id, rank=2, points=3,
                          matches_played=2, won=1, won_penalties=0, drawn=0, lost=1,
                          goals_for=2, goals_against=2),
    ])
    await session.commit()

    ranking = (await client.get("/ranking", headers=auth_header(user))).json()
    res = await client.get(f"/clubs/{club_id}", headers=auth_header(user))

    assert res.status_code == 200
    body = res.json()
    row = ranking[1]
    assert body["ranking_position"] == row["position"] == 2
    for field in ["points", "matches_played", "won", "won_penalties",
                  "drawn", "lost", "goals_for", "goals_against"]:
        assert body[field] == row[field]