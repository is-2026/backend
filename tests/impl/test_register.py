import uuid

import pytest
from sqlalchemy import func, select

from app.db.user import UserDB
from app.security.tokens import decode_access_token

URL = "/auth/register"
VALID = {"email": "ana@test.com", "password": "contraseña"}


async def _count_users(session) -> int:
    return await session.scalar(select(func.count()).select_from(UserDB))


async def test_valid_registration_returns_201_and_a_valid_token(client):
    r = await client.post(URL, json=VALID)

    assert r.status_code == 201
    payload = decode_access_token(r.json()["token"])
    uuid.UUID(payload["sub"])


async def test_valid_registration_stores_the_hashed_password(client, session):
    await client.post(URL, json=VALID)

    user = await session.scalar(select(UserDB).where(UserDB.email == VALID["email"]))

    assert user is not None
    assert user.hashed_password != VALID["password"]
    assert user.hashed_password.startswith("$argon2id$")


@pytest.mark.parametrize(
    "body",
    [
        {"password": "contraseña"},
        {"email": "ana@test.com"},
        {},
    ],
    ids=["sin_email", "sin_password", "vacio"],
)
async def test_missing_field_returns_400(client, session, body):
    r = await client.post(URL, json=body)

    assert r.status_code == 400
    assert "message" in r.json()
    assert await _count_users(session) == 0


async def test_existing_email_returns_409_and_does_not_create_account(client, session):
    session.add(UserDB(email=VALID["email"], hashed_password="da-igual"))
    await session.commit()

    r = await client.post(URL, json=VALID)

    assert r.status_code == 409
    assert "message" in r.json()
    assert await _count_users(session) == 1


async def test_email_is_normalized_so_case_variants_conflict(client, session):
    session.add(UserDB(email="ana@test.com", hashed_password="da-igual"))
    await session.commit()

    r = await client.post(
        URL, json={"email": "  Ana@Test.COM ", "password": "contraseña"}
    )

    assert r.status_code == 409
