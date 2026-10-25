import uuid
from functools import partial

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.security.tokens import create_access_token
from app.ws.close_codes import NORMAL, NOT_FOUND
from app.ws.match.router import router
from app.ws.match.runner import start_match

# app mínima porque la de app.main se conecta a MySQL al arrancar
app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def match_id(client, match_state, match_info):
    """Arranca un partido corto (20 ticks) y devuelve su id."""
    match_id = uuid.uuid4()
    match_state.total_ticks = 20
    # start_match necesita el event loop de la app: portal.call la corre ahí
    client.portal.call(
        partial(
            start_match,
            match_id,
            match_state,
            {},
            match_info,
            tick_interval=0.01,
            start_delay=0.2,
            cooling_break_duration=0,
            halftime_duration=0,
        )
    )
    # client.portal.call(...) existe porque start_match usa create_task, que necesita el event loop de la app.
    # El test corre en otro hilo, y portal.call es como decirle ejecutá esto allá adentro, en el loop de la app.
    # - partial(...) está porque portal.call no acepta argumentos con
    # nombre. partial arma una función con los argumentos ya cargados.
    return match_id


def connect(client, match_id):
    token = create_access_token(uuid.uuid4())
    return client.websocket_connect(f"/ws/matches/{match_id}?token={token}")


def receive_until_closed(ws) -> tuple[list[dict], int]:
    messages = []
    with pytest.raises(WebSocketDisconnect) as closed:
        while True:
            messages.append(ws.receive_json())
    return messages, closed.value.code


def test_unknown_match_closes_with_4404(client):
    with connect(client, uuid.uuid4()) as ws:
        _, code = receive_until_closed(ws)
    assert code == NOT_FOUND


def test_two_clients_receive_the_whole_match(client, match_id):
    with connect(client, match_id) as ws1, connect(client, match_id) as ws2:
        messages1, code1 = receive_until_closed(ws1)
        messages2, code2 = receive_until_closed(ws2)

    assert messages1 == messages2
    # al conectarse: matchStarted y el estado inicial
    assert [m["type"] for m in messages1[:2]] == ["matchStarted", "matchState"]
    assert messages1[1]["data"]["tick"] == 0
    assert messages1[-1]["type"] == "matchFinished"
    assert code1 == NORMAL
    assert code2 == NORMAL


def test_if_one_client_leaves_the_other_keeps_receiving(client, match_id):
    with connect(client, match_id) as ws1:
        with connect(client, match_id) as ws2:
            ws2.receive_json()  # matchStarted
            ws2.receive_json()  # matchState
        # ws2 ya se fue
        messages, code = receive_until_closed(ws1)

    assert messages[-1]["type"] == "matchFinished"
    assert code == NORMAL


def test_late_client_starts_from_current_tick(client, match_id):
    with connect(client, match_id) as ws1:
        for _ in range(7):  # ws1 va a leer matchStarted y del tick 0 al tick 5
            ws1.receive_json()
        with connect(client, match_id) as ws2:
            started = ws2.receive_json()
            first = ws2.receive_json()

    assert started["type"] == "matchStarted"
    assert started["data"]["tick"] >= 5
    assert first["type"] == "matchState"
    assert first["data"]["tick"] >= started["data"]["tick"]


def test_match_started_has_clubs_and_lineups(client, match_id):
    with connect(client, match_id) as ws:
        started = ws.receive_json()

    data = started["data"]
    assert started["type"] == "matchStarted"
    assert data["match_id"] == str(match_id)
    assert data["home_club"] == {
        "id": "club-local",
        "name": "Local",
        "avatar_url": "https://x/local.png",
    }
    assert len(data["home_lineup"]) == len(data["away_lineup"]) == 6
    assert data["total_ticks"] == 20
    assert data["status"] == "in_progress"
