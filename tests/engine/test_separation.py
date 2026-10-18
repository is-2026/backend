from math import hypot, sqrt

import pytest

from app.engine.actions import Move
from app.engine.constants import FIELD_HALF_LENGTH, FIELD_HALF_WIDTH, SOCIAL_DISTANCING
from app.engine.engine import step


def test_separation(state, rng):
    player1 = state.players[0]
    player1.x = 1.0
    player1.y = 0.0
    player2 = state.players[1]
    player2.x = -1.0
    player2.y = 0.0

    action1 = Move(dx=-1.0, dy=0.0, speed_pct=100.0)
    action2 = Move(dx=1.0, dy=0.0, speed_pct=100.0)
    step(state, {player1.id: action1, player2.id: action2}, rng)

    distance = hypot(player1.x - player2.x, player1.y - player2.y)
    assert distance == pytest.approx(SOCIAL_DISTANCING)


def test_3_player_separation(state, rng):
    player1 = state.players[0]
    player1.x = 1.0
    player1.y = 0.0
    player2 = state.players[1]
    player2.x = -1.0
    player2.y = 0.0
    player3 = state.players[2]
    player3.x = 0.0
    player3.y = 1.0

    action1 = Move(dx=-1.0, dy=0.0, speed_pct=100.0)
    action2 = Move(dx=1.0, dy=0.0, speed_pct=100.0)
    action3 = Move(dx=0.0, dy=-1.0, speed_pct=100.0)
    step(state, {player1.id: action1, player2.id: action2, player3.id: action3}, rng)

    distance1_2 = hypot(player1.x - player2.x, player1.y - player2.y)
    assert distance1_2 >= SOCIAL_DISTANCING - 1e-9
    distance1_3 = hypot(player1.x - player3.x, player1.y - player3.y)
    assert distance1_3 >= SOCIAL_DISTANCING - 1e-9
    distance2_3 = hypot(player2.x - player3.x, player2.y - player3.y)
    assert distance2_3 >= SOCIAL_DISTANCING - 1e-9


def test_move_and_slide(state, rng):
    player = state.players[0]
    obstacle = state.players[1]

    player.x = 0.0
    player.y = 0.0

    obstacle.x = 1.0
    obstacle.y = 0.0

    action = Move(dx=1.0, dy=1.0, speed_pct=100.0)

    step(state, {player.id: action}, rng)

    distance = hypot(player.x - obstacle.x, player.y - obstacle.y)

    assert distance >= SOCIAL_DISTANCING

    assert player.x == pytest.approx(0.0)
    assert player.y == pytest.approx(0.6 / sqrt(2))
    assert obstacle.x == pytest.approx(1.0)


def test_borders_with_separation(state, rng):
    player1 = state.players[0]
    player1.x = 20.0
    player1.y = 0.0
    player2 = state.players[1]
    player2.x = 18.8
    player2.y = 0.0

    action2 = Move(dx=1.0, dy=0.0, speed_pct=100.0)
    step(state, {player2.id: action2}, rng)

    distance = hypot(player1.x - player2.x, player1.y - player2.y)
    assert distance == pytest.approx(SOCIAL_DISTANCING)
    assert player1.x == FIELD_HALF_LENGTH
    assert abs(player1.y) <= FIELD_HALF_WIDTH
    assert player2.x == pytest.approx(19.0)
    assert abs(player2.y) <= FIELD_HALF_WIDTH
