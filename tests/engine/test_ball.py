import pytest

from app.engine.constants import (
    BALL_BOUNCE,
    BALL_FRICTION,
    FIELD_HALF_LENGTH,
    FIELD_HALF_WIDTH,
)
from app.engine.engine import step

# velocidad de una pelota que pegó a 10 m/s: rebota y después frena (= 7.6)
BOUNCED_SPEED = 10.0 * BALL_BOUNCE * BALL_FRICTION


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
