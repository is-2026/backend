import pytest

from app.engine.constants import TRIANGLE_HOME
from app.engine.engine import _reset_positions, kickoff, step


def test_tick_advances(state, rng):
    step(state, {}, rng)

    assert state.tick == 1


def test_reset_positions(state):
    # desordenamos todo, jugadores, pelota y cooldowns
    for player in state.players:
        player.x, player.y = 7.0, 7.0
        player.cooldown = 5
    ball = state.ball
    ball.x, ball.y, ball.vx, ball.vy = 3.0, -2.0, 10.0, 4.0
    ball.last_touch_id = "h1"

    _reset_positions(state)

    home = [p for p in state.players if p.side == "home"]
    away = [p for p in state.players if p.side == "away"]
    assert [(p.x, p.y) for p in home] == list(TRIANGLE_HOME)
    # el visitante usa la misma formación pero espejada
    assert [(p.x, p.y) for p in away] == [(-x, -y) for x, y in TRIANGLE_HOME]
    assert all(p.cooldown == 0 for p in state.players)
    assert (ball.x, ball.y, ball.vx, ball.vy) == (0.0, 0.0, 0.0, 0.0)
    assert ball.last_touch_id is None


def test_kickoff_leaves_match_ready_to_start(state):
    for player in state.players:
        player.x, player.y = 7.0, 7.0
    state.ball.x, state.ball.vx = 3.0, 10.0
    state.tick = 500
    state.home_score, state.away_score = 2, 1

    kickoff(state)

    home = [p for p in state.players if p.side == "home"]
    away = [p for p in state.players if p.side == "away"]
    assert [(p.x, p.y) for p in home] == list(TRIANGLE_HOME)
    assert [(p.x, p.y) for p in away] == [(-x, -y) for x, y in TRIANGLE_HOME]
    assert (state.ball.x, state.ball.y, state.ball.vx, state.ball.vy) == (0, 0, 0, 0)
    assert state.tick == 0
    assert (state.home_score, state.away_score) == (0, 0)
