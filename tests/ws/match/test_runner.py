import uuid

import pytest

from app.ws.close_codes import NORMAL
from app.ws.match import runner
from app.ws.match.runner import (
    LiveMatch,
    live_matches,
    match_connections,
    run_match,
    start_match,
)
from tests.ws.conftest import FakeWebSocket

TOTAL_TICKS = 5


@pytest.fixture
def match_id():
    return uuid.uuid4()


@pytest.fixture
def live(match_id, match_state):
    match_state.total_ticks = TOTAL_TICKS
    live = LiveMatch(match_id=match_id, state=match_state, brains={})
    live_matches[match_id] = live
    return live


@pytest.fixture
def client(match_id):
    ws = FakeWebSocket()
    match_connections.connect(match_id, ws)
    return ws


async def test_sends_one_match_state_per_tick(live, client):
    await run_match(live, tick_interval=0, start_delay=0)

    states = [m for m in client.sent if m["type"] == "matchState"]
    assert [m["data"]["tick"] for m in states] == [1, 2, 3, 4, 5]
    assert live.last_state == states[-1]  # queda guardado para el que se conecte


async def test_sends_match_finished_and_closes_at_the_end(live, client, match_id):
    await run_match(live, tick_interval=0, start_delay=0)

    assert client.sent[-1]["type"] == "matchFinished"
    assert client.sent[-1]["data"]["tick"] == TOTAL_TICKS
    assert client.closed_code == NORMAL
    assert match_id not in live_matches


async def test_start_match_sets_tick_0_and_runs_in_background(
    match_state, match_id, client
):
    match_state.total_ticks = TOTAL_TICKS
    match_state.home_score = 3  # kickoff lo tiene que resetear

    live = start_match(match_id, match_state, {}, tick_interval=0, start_delay=0)

    assert live_matches[match_id] is live
    assert live.last_state["data"]["tick"] == 0
    assert match_state.home_score == 0

    await live.task

    assert client.sent[-1]["type"] == "matchFinished"
    assert match_id not in live_matches
