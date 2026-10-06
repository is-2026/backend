import uuid

import pytest
from sqlalchemy import func, select

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.security.tokens import create_access_token

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
