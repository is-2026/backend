from app.engine.events import GoalEvent
from app.ws.match.messages import goal_message, match_state_message

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
