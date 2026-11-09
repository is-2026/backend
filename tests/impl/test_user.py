import uuid

import pytest

from app.db.user import UserDB
from app.security.tokens import create_access_token

URL = "/user"


# creacion de usuario en la base de test
@pytest.fixture
async def user(session):
    user = UserDB(email="hola@prueba.com", hashed_password="hash")
    session.add(user)
    await session.commit()
    return user


# arma el header con un token valido para ese id
def auth_header(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# peticion GET /user con token: debe devolver id y email
async def test_get_my_user_returns_200(client, user):
    r = await client.get(URL, headers=auth_header(user.id))
    assert r.status_code == 200
    assert r.json() == {"id": str(user.id), "email": "hola@prueba.com"}


#token valido pero el usuario no existe: debe responder 404
async def test_get_my_user_not_found_returns_404(client):
    r = await client.get(URL, headers=auth_header(uuid.uuid4()))
    assert r.status_code == 404
    assert r.json()["message"] == "El usuario no existe"


# peticion GET /user sin token: debe responder 401
async def test_get_my_user_without_token_returns_401(client):
    r = await client.get(URL)
    assert r.status_code == 401
    assert "No autorizado" in r.json()["message"]