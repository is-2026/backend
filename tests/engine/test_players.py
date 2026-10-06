from math import sqrt

import pytest

from app.engine.actions import Move
from app.engine.constants import (
    FIELD_HALF_LENGTH,
    FIELD_HALF_WIDTH,
    SPEED_MAX_RANGE,
)
from app.engine.engine import _scale, step


def test_scale_maps_min_and_max():
    assert _scale(20, SPEED_MAX_RANGE) == 4.0
    assert _scale(100, SPEED_MAX_RANGE) == 8.0


def test_move_advances_max_speed_times_dt(state, rng):
    player = state.players[0]  # speed 60 -> 6 m/s -> 0.6 m por tick
    x_before, y_before = player.x, player.y

    step(state, {player.id: Move(1, 0, 100)}, rng)

    assert player.x == pytest.approx(x_before + 0.6)
    assert player.y == pytest.approx(y_before)


@pytest.mark.parametrize(
    "initial_x, initial_y, dx, dy, expected_x, expected_y",
    [
        # Límite X Positivo (Derecha): 19.8 + 0.6 = 20.4 -> debe quedar en 20.0
        (19.8, 0.0, 1.0, 0.0, FIELD_HALF_LENGTH, 0.0),
        # Límite X Negativo (Izquierda): -19.8 - 0.6 = -20.4 -> debe quedar en -20.0
        (-19.8, 0.0, -1.0, 0.0, -FIELD_HALF_LENGTH, 0.0),
        # Límite Y Positivo (Arriba): 9.8 + 0.6 = 10.4 -> debe quedar en 10.0
        (0.0, 9.8, 0.0, 1.0, 0.0, FIELD_HALF_WIDTH),
        # Límite Y Negativo (Abajo): -9.8 - 0.6 = -10.4 -> debe quedar en -10.0
        (0.0, -9.8, 0.0, -1.0, 0.0, -FIELD_HALF_WIDTH),
        # Esquina en Diagonal (Prueba los dos ejes al mismo tiempo)
        (19.8, 9.8, 1.0, 1.0, FIELD_HALF_LENGTH, FIELD_HALF_WIDTH),
        # Caso "deslizamiento" (Se topa con un borde y sigue en el otro libre)
        (19.8, 0, 1.0, 1.0, FIELD_HALF_LENGTH, 0.6 / sqrt(2)),
    ],
)
def test_borders(state, rng, initial_x, initial_y, dx, dy, expected_x, expected_y):
    player = state.players[0]
    player.x = initial_x
    player.y = initial_y

    action = Move(dx=dx, dy=dy, speed_pct=100.0)
    step(state, {player.id: action}, rng)

    assert player.x == pytest.approx(expected_x)
    assert player.y == pytest.approx(expected_y)


def test_pct_speed(state, rng):
    player1, player2 = state.players[0], state.players[1]
    player1.x, player1.y = 0.0, 0.0
    player2.x, player2.y = 0.0, 0.0

    step(state, {player1.id: Move(1, 1, 100), player2.id: Move(1, 1, 150)}, rng)

    assert player1.x == pytest.approx(player2.x)
    assert player1.y == pytest.approx(player2.y)


def test_negative_pct_does_not_move(state, rng):
    player = state.players[0]
    x_before, y_before = player.x, player.y

    step(state, {player.id: Move(1, 0, -50)}, rng)

    assert player.x == x_before
    assert player.y == y_before
