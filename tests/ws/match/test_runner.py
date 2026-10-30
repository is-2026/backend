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

TOTAL_TICKS = 5  # pausas después de los ticks 1, 2 y 3

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

    live = start_match(match_id, match_state, {}, match_info, **NO_WAIT)

    assert live_matches[match_id] is live
    assert live.last_state["data"]["tick"] == 0

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


def summary(sent: list[dict]) -> list[tuple[str, int]]:
    return [(m["type"], m["data"]["tick"]) for m in sent]


async def test_pauses_after_each_quarter(live, client):
    await run_match(live, **NO_WAIT)

    # entre el inicio de la pausa y matchResumed no hay matchState
    # y el tick no avanza
    assert summary(client.sent) == [
        ("matchState", 1),
        ("coolingBreakStart", 1),
        ("matchResumed", 1),
        ("matchState", 2),
        ("halftimeStart", 2),
        ("matchResumed", 2),
        ("matchState", 3),
        ("coolingBreakStart", 3),
        ("matchResumed", 3),
        ("matchState", 4),
        ("matchState", 5),
        ("matchFinished", 5),
    ]
    breaks = [m for m in client.sent if m["type"] == "coolingBreakStart"]
    assert [m["data"]["cooling_break_number"] for m in breaks] == [1, 2]
    resumed = [m for m in client.sent if m["type"] == "matchResumed"]
    assert [m["data"]["resume_type"] for m in resumed] == [
        "after_cooling_break_1",
        "after_halftime",
        "after_cooling_break_2",
    ]


async def test_each_pause_last_its_duration_and_play_resumes(live, client):
    await run_match(
        live,
        tick_interval=0.02,
        start_delay=0,
        cooling_break_duration=0.1,
        halftime_duration=0.2,
    )

    types = [m["type"] for m in client.sent]
    for start_type, duration in [("coolingBreakStart", 0.1), ("halftimeStart", 0.2)]:
        i = types.index(start_type)
        assert types[i + 1] == "matchResumed"
        assert client.times[i + 1] - client.times[i] == pytest.approx(
            duration, abs=0.03
        )
        assert types[i + 2] == "matchState"
