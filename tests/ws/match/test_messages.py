from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.engine.events import GoalEvent
from app.engine.state import Side
from app.ws.match.messages import (
    behavior_changed_message,
    goal_message,
    match_finished_message,
    match_resumed_message,
    match_started_message,
    match_state_message,
    pause_start_message,
    substitution_made_message,
)
from app.ws.match.pauses import Pause
from app.ws.match.substitutions import PendingSubstitution

MATCH_ID = "partido-1"


def test_match_state_has_all_attributes(match_state):
    match_state.tick = 42

    msg = match_state_message(MATCH_ID, match_state)

    assert msg.type == "matchState"
    assert msg.data.match_id == MATCH_ID
    assert msg.data.tick == 42
    assert [p.player_id for p in msg.data.players] == [
        "h1",
        "h2",
        "h3",
        "a1",
        "a2",
        "a3",
    ]
    h2 = msg.data.players[1]
    assert (h2.position.x, h2.position.y) == (-12, -5)
    assert (msg.data.ball_position.x, msg.data.ball_position.y) == (3.5, -1.25)


def test_match_state_serializes_to_json_as_intended(match_state):
    payload = match_state_message(MATCH_ID, match_state).model_dump(mode="json")

    assert payload["type"] == "matchState"
    assert set(payload["data"]) == {"match_id", "tick", "players", "ball_position"}
    assert payload["data"]["players"][0] == {
        "player_id": "h1",
        "position": {"x": -4.0, "y": 0.0},
    }
    assert payload["data"]["ball_position"] == {"x": 3.5, "y": -1.25}


def test_goal_has_all_attributes(match_state):
    match_state.tick = 42
    match_state.home_score = 1
    match_state.away_score = 2
    event = GoalEvent(tick=41, player_id="a2", team_id="club-visitante", minute=0)

    msg = goal_message(MATCH_ID, event, match_state)

    assert msg.type == "goal"
    assert msg.data.match_id == MATCH_ID
    assert msg.data.player_id == "a2"
    assert msg.data.team_id == "club-visitante"
    assert (msg.data.home_score, msg.data.away_score) == (1, 2)


def test_goal_serializes_to_json_as_intended(match_state):
    event = GoalEvent(tick=0, player_id="a1", team_id="club-visitante", minute=0)

    payload = goal_message(MATCH_ID, event, match_state).model_dump(mode="json")

    assert payload["type"] == "goal"
    assert set(payload["data"]) == {
        "match_id",
        "tick",
        "player_id",
        "team_id",
        "minute",
        "home_score",
        "away_score",
    }


def test_match_finished_has_final_result(match_state):
    match_state.tick = 3000
    match_state.home_score = 2
    match_state.away_score = 3

    msg = match_finished_message(MATCH_ID, match_state)

    assert msg.type == "matchFinished"
    assert msg.data.match_id == MATCH_ID
    assert msg.data.tick == 3000
    assert (msg.data.home_score, msg.data.away_score) == (2, 3)
    assert msg.data.status == "finished"


def test_match_finished_serialzes_to_json_as_intended(match_state):
    payload = match_finished_message(MATCH_ID, match_state).model_dump(mode="json")

    assert payload["type"] == "matchFinished"
    assert set(payload["data"]) == {
        "match_id",
        "tick",
        "match_end",
        "home_score",
        "away_score",
        "home_penalties",
        "away_penalties",
        "winner_club_id",
        "status",
    }
    assert payload["data"]["status"] == "finished"
    assert payload["data"]["home_penalties"] is None
    assert payload["data"]["away_penalties"] is None


def test_match_started_serializes_to_json_as_intended(match_state, match_info):
    match_state.tick = 7
    match_state.home_score = 2
    start = datetime(2026, 10, 4, 18, 30, 33, tzinfo=timezone.utc)

    payload = match_started_message(
        MATCH_ID, match_info, start, match_state
    ).model_dump(mode="json", exclude_none=True)

    assert payload["type"] == "matchStarted"
    assert set(payload["data"]) == {
        "match_id",
        "home_club",
        "away_club",
        "home_lineup",
        "away_lineup",
        "match_start",
        "tick",
        "total_ticks",
        "home_score",
        "away_score",
        "status",
    }
    data = payload["data"]
    assert data["match_start"] == "2026-10-04T18:30:33Z"
    assert (data["tick"], data["total_ticks"]) == (7, 3000)
    assert (data["home_score"], data["away_score"], data["status"]) == (
        2,
        0,
        "in_progress",
    )
    assert data["home_lineup"][0] == {
        "player_id": "h1",
        "number": 1,
        "name": "Jugador h1",
        "is_starter": True,
        "power": 60,
        "agility": 60,
        "control": 60,
        "speed": 60,
        "strength": 60,
        "behavior_id": "b-h1",
        "behavior_name": "Atacante",
    }


@pytest.mark.parametrize(
    "pause, number", [(Pause.COOLING_BREAK_1, 1), (Pause.COOLING_BREAK_2, 2)]
)
def test_cooling_break_start_has_its_number_and_end(match_state, pause, number):
    match_state.tick = 750

    msg = pause_start_message(MATCH_ID, match_state, pause, 15)

    assert msg.type == "coolingBreakStart"
    assert (msg.data.match_id, msg.data.tick) == (MATCH_ID, 750)
    assert msg.data.cooling_break_number == number
    assert msg.data.ends_at - msg.data.cooling_break_start == timedelta(seconds=15)


def test_halftime_start_serializes_as_asyncapi(match_state):
    match_state.tick = 1500

    msg = pause_start_message(MATCH_ID, match_state, Pause.HALFTIME, 15)
    payload = msg.model_dump(mode="json")

    assert payload["type"] == "halftimeStart"
    assert set(payload["data"]) == {"match_id", "tick", "halftime_start", "ends_at"}
    start = datetime.fromisoformat(payload["data"]["halftime_start"])
    ends_at = datetime.fromisoformat(payload["data"]["ends_at"])
    assert ends_at - start == timedelta(seconds=15)


@pytest.mark.parametrize(
    "pause, resume_type",
    [
        (Pause.COOLING_BREAK_1, "after_cooling_break_1"),
        (Pause.HALFTIME, "after_halftime"),
        (Pause.COOLING_BREAK_2, "after_cooling_break_2"),
    ],
)
def test_match_resumed_says_which_pause_ended(match_state, pause, resume_type):
    match_state.tick = 1500

    msg = match_resumed_message(MATCH_ID, match_state, pause)

    assert msg.type == "matchResumed"
    assert (msg.data.tick, msg.data.resume_type) == (1500, resume_type)


def test_match_started_can_say_paused(match_state, match_info):
    start = datetime.now(timezone.utc)

    msg = match_started_message(MATCH_ID, match_info, start, match_state, "paused")

    assert msg.data.status == "paused"


def test_substitution_made_has_the_players_and_the_behavior(match_state):
    sub = PendingSubstitution(
        id="s1",
        player_out_id="h1",
        player_in_id="h4",
        behavior_id="b-1",
        behavior_name="Atacante",
        behavior_code="def decide_action():\n    pass\n",
        window=Pause.HALFTIME,
    )

    data = substitution_made_message(MATCH_ID, match_state, sub).data

    assert data.player_out_id == "h1"
    assert data.player_in_id == "h4"
    assert data.behavior_id == "b-1"
    assert data.behavior_name == "Atacante"


def test_behavior_changed_serializes_as_asyncapi(match_state):
    match_state.tick = 912

    payload = behavior_changed_message(
        MATCH_ID, match_state, "h1", "b-nuevo", "Defensor"
    ).model_dump(mode="json")

    assert payload == {
        "type": "behaviorChanged",
        "data": {
            "match_id": MATCH_ID,
            "tick": 912,
            "player_id": "h1",
            "behavior_id": "b-nuevo",
            "behavior_name": "Defensor",
        },
    }


@pytest.mark.parametrize(
    "home_score, away_score, winner",
    [(2, 1, "club-local"), (1, 2, "club-visitante"), (1, 1, None)],
)
def test_match_finished_winner_by_goals(match_state, home_score, away_score, winner):
    match_state.home_score, match_state.away_score = home_score, away_score

    msg = match_finished_message(MATCH_ID, match_state)

    assert msg.data.winner_club_id == winner


def test_match_finished_after_penalties(match_state):
    match_state.home_score = match_state.away_score = 1
    shootout = SimpleNamespace(home_penalties=3, away_penalties=4, winner=Side.AWAY)

    msg = match_finished_message(MATCH_ID, match_state, shootout)

    assert (msg.data.home_score, msg.data.away_score) == (1, 1)
    assert (msg.data.home_penalties, msg.data.away_penalties) == (3, 4)
    assert msg.data.winner_club_id == "club-visitante"
