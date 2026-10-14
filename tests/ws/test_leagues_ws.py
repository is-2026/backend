import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.security.tokens import create_access_token
from app.ws import leagues_ws
from app.ws.lobby_league import league_lobby_connection

LEAGUE = uuid.uuid4()  # liga not_started
LEAGUE_STARTED = uuid.uuid4()


class _FakeSession:  # para simular la consulta
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeLeagueRepository:
    """Existen ligas no iniciadas y ligas iniciadas"""

    def __init__(self, session=None):
        self._session = session

    async def get(self, league_id: uuid.UUID):
        if league_id == LEAGUE:
            return SimpleNamespace(status="not_started")
        if league_id == LEAGUE_STARTED:
            return SimpleNamespace(status="started")
        return None


@pytest.fixture(autouse=True)  # para q se corra solo siempre antes de los tests
def clean_lobby():
    league_lobby_connection._connections.clear()  # para borrar cualquier conexion que pueda hacer un test anterior
    yield  # ejecuto el test
    league_lobby_connection._connections.clear()


@pytest.fixture
def client(
    monkeypatch,
):  # monkeypatch reemplaza cosas independientemente, mientras se corre el test, y al final las restaura
    monkeypatch.setattr(leagues_ws, "SessionLocal", _FakeSession)
    monkeypatch.setattr(
        leagues_ws, "LeagueRepository", _FakeLeagueRepository
    )  # CAMBIO EN DONDE VOY A UTILIZAR

    app = FastAPI()
    app.include_router(leagues_ws.router)

    with TestClient(
        app
    ) as client:  # simulo un cliente para no levantar un servidor real
        yield client


def _url(league_id: uuid.UUID, token=None):
    url = f"/ws/leagues/{league_id}/lobby"
    return f"{url}?token={token}" if token else url  # el token viene en la url


def _close_code(
    client, url
) -> int:  # Devuelve con qué código cerró el servidor la conexión.
    with client.websocket_connect(url) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
    return exc_info.value.code


def _wait_until_connected(league_id, count):
    # El endpoint anota la conexión en el manager un instante DESPUÉS de aceptarla.
    # Entonces espero (hasta ~1 segundo) a que haya exactamente "count"
    # conexiones anotadas para esa liga.
    for _ in range(100):
        if len(league_lobby_connection._connections.get(league_id, ())) == count:
            return
        time.sleep(0.01)
    # si pasó el tiempo y no se cumplió, el test falla con este mensaje
    raise AssertionError("los clientes no se registraron en el lobby")


def test_not_token_close(client):
    assert _close_code(client, _url(LEAGUE)) == 4401


def test_league_not_exist(client):
    token = create_access_token(uuid.uuid4())  # token valido
    assert _close_code(client, _url(uuid.uuid4(), token)) == 4404


def test_league_started(client):
    token = create_access_token(uuid.uuid4())  # token valido
    assert _close_code(client, _url(LEAGUE_STARTED, token)) == 4404


def test_league_not_started_token_valid(client):
    token = create_access_token(uuid.uuid4())  # token valido
    with client.websocket_connect(_url(LEAGUE, token)):
        _wait_until_connected(
            LEAGUE, 1
        )  # Espero a que haya 1 conexión anotada para esa liga.


def test_client_disconnect_lobby(client):
    token = create_access_token(uuid.uuid4())  # token valido
    with client.websocket_connect(_url(LEAGUE, token)):
        _wait_until_connected(
            LEAGUE, 1
        )  # Espero a que haya 1 conexión anotada para esa liga.

    _wait_until_connected(
        LEAGUE, 0
    )  # espero que queden 0 conexiones porque el finally del endpoint lo va a sacar.
