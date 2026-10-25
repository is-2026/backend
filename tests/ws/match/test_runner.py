import uuid
from datetime import datetime, timezone

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

NO_WAIT = {
    "tick_interval": 0,
    "start_delay": 0,
    "cooling_break_duration": 0,
    "halftime_duration": 0,
}


@pytest.fixture
def match_id():
    return uuid.uuid4()


@pytest.fixture
def live(match_id, match_state, match_info):
    match_state.total_ticks = TOTAL_TICKS
    live = LiveMatch(
        match_id=match_id,
        state=match_state,
        brains={},
        info=match_info,
        match_start=datetime.now(timezone.utc),
    )
    live_matches[match_id] = live
    return live


@pytest.fixture
def client(match_id):
    ws = FakeWebSocket()
    match_connections.connect(match_id, ws)
    return ws


async def test_sends_one_match_state_per_tick(live, client):
    await run_match(live, **NO_WAIT)

    states = [m for m in client.sent if m["type"] == "matchState"]
    assert [m["data"]["tick"] for m in states] == [1, 2, 3, 4, 5]
    assert live.last_state == states[-1]  # queda guardado para el que se conecte


async def test_sends_match_finished_and_closes_at_the_end(live, client, match_id):
    await run_match(live, **NO_WAIT)

    assert client.sent[-1]["type"] == "matchFinished"
    assert client.sent[-1]["data"]["tick"] == TOTAL_TICKS
    assert client.closed_code == NORMAL
    assert match_id not in live_matches


async def test_start_match_sets_tick_0_and_runs_in_background(
    match_state, match_info, match_id, client
):
    match_state.total_ticks = TOTAL_TICKS
    match_state.home_score = 3  # kickoff lo tiene que resetear

    live = start_match(match_id, match_state, {}, match_info, **NO_WAIT)

    assert live_matches[match_id] is live
    assert live.last_state["data"]["tick"] == 0
    assert match_state.home_score == 0

    await live.task

    assert client.sent[-1]["type"] == "matchFinished"
    assert match_id not in live_matches


async def test_start_match_saves_info_and_match_start(
    match_state, match_info, match_id
):
    before = datetime.now(timezone.utc)

    live = start_match(match_id, match_state, {}, match_info, start_delay=60)
    live.task.cancel()
    live_matches.pop(match_id)

    assert live.info is match_info
    # el partido arranca después de la espera
    assert (live.match_start - before).total_seconds() == pytest.approx(60, abs=1)


def test_started_payload_uses_current_tick_and_score(live):
    live.state.tick = 120
    live.state.away_score = 1

    payload = runner.started_payload(live)

    assert payload["type"] == "matchStarted"
    assert payload["data"]["tick"] == 120
    assert payload["data"]["away_score"] == 1
    # los suplentes no tienen comportamiento: no se mandan esos campos
    sub = payload["data"]["home_lineup"][3]
    assert sub["is_starter"] is False
    assert "behavior_id" not in sub
