import pytest

from app.engine.actions import Move
from app.engine.constants import SPEED_MAX_RANGE
from app.engine.engine import _scale, step


def test_scale_maps_min_and_max():
    assert _scale(20, SPEED_MAX_RANGE) == 4.0
    assert _scale(100, SPEED_MAX_RANGE) == 8.0


def test_tick_advances(state, rng):
    step(state, {}, rng)

    assert state.tick == 1


def test_move_advances_max_speed_times_dt(state, rng):
    player = state.players[0]  # speed 60 -> 6 m/s -> 0.6 m por tick
    x_before, y_before = player.x, player.y

    step(state, {player.id: Move(1, 0, 100)}, rng)

    assert player.x == pytest.approx(x_before + 0.6)
    assert player.y == pytest.approx(y_before)
