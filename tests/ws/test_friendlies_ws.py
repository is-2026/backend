#tests del lobby
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.security.tokens import create_access_token
from app.ws import friendlies_ws
from app.ws.lobby_friendly import lobby_connection
from types import SimpleNamespace

EXISTING_FRIENDLY = uuid.uuid4()  # esperando rival
ACCEPTED_FRIENDLY = uuid.uuid4()  # ya se unió el rival
CREATOR_USER, RIVAL_USER = uuid.uuid4(), uuid.uuid4()
CREATOR_CLUB, RIVAL_CLUB = uuid.uuid4(), uuid.uuid4()
CLUB_NAMES = {CREATOR_CLUB: "Creador FC", RIVAL_CLUB: "Rival FC"}

class _FakeSession: #para simular la consulta
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeFriendlyRepository:
    """Solo existen EXISTING_FRIENDLY (sin rival) y ACCEPTED_FRIENDLY (con rival)."""

    def __init__(self, session=None):
        self.session = session
 
    async def get(self, friendly_id):
        if friendly_id == EXISTING_FRIENDLY:
            return SimpleNamespace(creator_club_id=CREATOR_CLUB, rival_club_id=None)
        if friendly_id == ACCEPTED_FRIENDLY:
            return SimpleNamespace(
                creator_club_id=CREATOR_CLUB, rival_club_id=RIVAL_CLUB
            )
        return None

    async def get_club_name(self, club_id):
        return CLUB_NAMES.get(club_id)


class _FakeClubRepository:
    """El club de cada usuario: el creador y el que se unió."""

    def __init__(self, session=None):
        self.session = session

    async def get_by_user_id(self, user_id):
        clubs = {CREATOR_USER: CREATOR_CLUB, RIVAL_USER: RIVAL_CLUB}
        return SimpleNamespace(id=clubs[user_id]) if user_id in clubs else None

@pytest.fixture(autouse=True)
def clean_lobby():
    lobby_connection._connections.clear()
    yield
    lobby_connection._connections.clear()

@pytest.fixture
def client(monkeypatch):
    # sin MySQL: reemplazamos la sesión y el repositorio que usa el endpoint
    monkeypatch.setattr(friendlies_ws, "SessionLocal", _FakeSession) #piso los nombres
    monkeypatch.setattr(friendlies_ws, "FriendlyRepository", _FakeFriendlyRepository)
    monkeypatch.setattr(friendlies_ws, "ClubRepository", _FakeClubRepository)
    app = FastAPI()  # app mínima: la de main.py se conecta a MySQL al arrancar
    app.include_router(friendlies_ws.router)
    with TestClient(app) as client:
        yield client


def _url(friendly_id, token=None): #retorna la url con o sin token 
    url = f"/ws/friendlies/{friendly_id}/lobby"
    return f"{url}?token={token}" if token else url


def _close_code(client, url) -> int: #abre el ws para leer, como el endpoint hace accept() y cierra con un codigo, debo recibir ese codigo
    with client.websocket_connect(url) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
    return exc_info.value.code


def _wait_until_connected(friendly_id, count):
    """El connect al manager pasa después del accept: esperamos a que se registren."""
    for _ in range(100): #espero q se conecten
        if len(lobby_connection._connections.get(friendly_id, ())) == count:
            return
        time.sleep(0.01)
    raise AssertionError("los clientes no se registraron en el lobby")

def test_without_token_closes_with_4401(client):  #conexion sin token
    assert _close_code(client, _url(EXISTING_FRIENDLY)) == 4401
 
 
def test_invalid_token_closes_with_4401(client): #conexion con token invalido
    assert _close_code(client, _url(EXISTING_FRIENDLY, "basura")) == 4401
 
 
def test_unknown_friendly_closes_with_4404(client): #token valido pero amistoso no
    token = create_access_token(uuid.uuid4())
 
    assert _close_code(client, _url(uuid.uuid4(), token)) == 4404
 
 
def test_valid_connection_is_registered_in_lobby(client): #conexion con token valido y amistoso existente
    token = create_access_token(uuid.uuid4())
 
    with client.websocket_connect(_url(EXISTING_FRIENDLY, token)):
        _wait_until_connected(EXISTING_FRIENDLY, 1)
        #no ponemos assert porque si el endpoint no llama a lobby_connection.connect lanza un error
 
 
def test_client_is_removed_from_lobby_on_disconnect(client): #caso que se hayan conectados los 2 pero 1 sale en el lobby
    token = create_access_token(uuid.uuid4())
 
    with client.websocket_connect(_url(EXISTING_FRIENDLY, token)):
        _wait_until_connected(EXISTING_FRIENDLY, 1)
 
    # al salir del with el cliente se fue: el finally del endpoint debe limpiar
    _wait_until_connected(EXISTING_FRIENDLY, 0)


@pytest.mark.parametrize(
    ("user_id", "expected_club", "expected_name"),
    [
        (CREATOR_USER, RIVAL_CLUB, "Rival FC"),  # el creador ve al que se unió
        (RIVAL_USER, CREATOR_CLUB, "Creador FC"),  # el que se unió ve al creador
    ],
)
def test_connect_after_join_sends_the_other_club(
    client, user_id, expected_club, expected_name
):
    token = create_access_token(user_id)

    with client.websocket_connect(_url(ACCEPTED_FRIENDLY, token)) as ws:
        message = ws.receive_json()

    assert message["type"] == "friendlyClubRegistered"
    assert message["data"]["club_id"] == str(expected_club)
    assert message["data"]["club_name"] == expected_name
