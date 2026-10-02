from math import sqrt

import pytest

from app.engine.actions import Move
from app.engine.constants import (
    ATTR_MAX,
    ATTR_MIN,
    BALL_BOUNCE,
    BALL_FRICTION,
    BALL_STOP_SPEED,
    CONTROL_RADIUS_RANGE,
    COOLDOWN_TICKS_RANGE,
    DT,
    FIELD_HALF_LENGTH,
    FIELD_HALF_WIDTH,
    GOAL_HALF_WIDTH,
    KICK_SPEED_RANGE,
    SPEED_MAX_RANGE,
    TICKS_PER_MINUTE,
    TICKS_PER_SECOND,
    TRIANGLE_HOME,
)
from app.engine.engine import _scale, step

# velocidad de una pelota que pegó a 10 m/s: rebota y después frena (= 7.6)
BOUNCED_SPEED = 10.0 * BALL_BOUNCE * BALL_FRICTION


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


def test_still_ball(state, rng):
    ball = state.ball
    x_before, y_before = ball.x, ball.y
    ball.vx, ball.vy = 0.0, 0.0

    step(state, {}, rng)
    assert x_before == ball.x
    assert y_before == ball.y


def test_friction_ball(state, rng):
    ball = state.ball
    ball.x, ball.y = 0.0, 0.0  # en teoría no hace falta
    ball.vx = 10.0
    step(state, {}, rng)
    assert ball.vx == pytest.approx(9.5)
    for _ in range(200):
        step(state, {}, rng)

    assert ball.vx == 0.0


def test_ball_advances_with_its_velocity(state, rng):
    ball = state.ball
    ball.x, ball.y = 0.0, 0.0
    ball.vx, ball.vy = 10.0, -5.0

    step(state, {}, rng)

    assert ball.x == pytest.approx(1.0)  # 10m/s * 0.1s
    assert ball.y == pytest.approx(-0.5)


@pytest.mark.parametrize(
    "x, y, vx, vy, expected_x, expected_y, expected_vx, expected_vy",
    [
        # borde derecho (y = 5: fuera del arco, para que no sea gol)
        (19.5, 5.0, 10.0, 0.0, FIELD_HALF_LENGTH, 5.0, -BOUNCED_SPEED, 0.0),
        # borde izquierdo
        (-19.5, 5.0, -10.0, 0.0, -FIELD_HALF_LENGTH, 5.0, BOUNCED_SPEED, 0.0),
        # borde de arriba
        (0.0, 9.5, 0.0, 10.0, 0.0, FIELD_HALF_WIDTH, 0.0, -BOUNCED_SPEED),
        # borde de abajo
        (0.0, -9.5, 0.0, -10.0, 0.0, -FIELD_HALF_WIDTH, 0.0, BOUNCED_SPEED),
        # esquina: rebota en los dos ejes
        (
            19.5,
            9.5,
            10.0,
            10.0,
            FIELD_HALF_LENGTH,
            FIELD_HALF_WIDTH,
            -BOUNCED_SPEED,
            -BOUNCED_SPEED,
        ),
    ],
)
def test_ball_bounces_on_borders(
    state, rng, x, y, vx, vy, expected_x, expected_y, expected_vx, expected_vy
):
    ball = state.ball
    ball.x, ball.y, ball.vx, ball.vy = x, y, vx, vy

    step(state, {}, rng)

    assert ball.x == pytest.approx(expected_x)
    assert ball.y == pytest.approx(expected_y)
    assert ball.vx == pytest.approx(expected_vx)
    assert ball.vy == pytest.approx(expected_vy)


def test_bounce_only_slows_the_component_that_hits(state, rng):
    ball = state.ball
    ball.x, ball.y, ball.vx, ball.vy = 19.5, 5.0, 10.0, 2.0

    step(state, {}, rng)

    assert ball.vx == pytest.approx(-BOUNCED_SPEED)
    assert ball.vy == pytest.approx(2.0 * BALL_FRICTION)  # solo fricción, sin rebote
    assert ball.y == pytest.approx(5.2)  # sigue avanzando a lo largo del borde
