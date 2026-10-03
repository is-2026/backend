import random
from math import hypot

import pytest

from app.engine.actions import Move, PassTo, Shoot, ShootAtGoal
from app.engine.constants import BALL_FRICTION
from app.engine.engine import step
from app.engine.state import Side
from tests.engine.conftest import make_player

# Power 60 -> la pelota sale a 17.5 m/s; en el mismo tick ya le aplica la fricción
SHOT_SPEED_AFTER_TICK = 17.5 * BALL_FRICTION


def _ball_next_to_h1(state):
    """h1 está en (-4, 0): la pelota a 0.5 m, dentro de su radio (1.0 con Control 60)."""
    state.ball.x, state.ball.y = -4.5, 0.0
    return state.players[0]


@pytest.mark.parametrize("power_pct", [100, 150])  # 150 se recorta a 100
def test_shoot_sets_ball_speed(state, rng, power_pct):
    h1 = _ball_next_to_h1(state)

    step(state, {h1.id: Shoot(1, 0, power_pct)}, rng)

    assert state.ball.vx == pytest.approx(SHOT_SPEED_AFTER_TICK)
    assert state.ball.vy == pytest.approx(0.0)


def test_kick_sets_last_touch_and_cooldown(state, rng):
    h1 = _ball_next_to_h1(state)

    step(state, {h1.id: Shoot(1, 0, 100)}, rng)

    assert state.ball.last_touch_id == "h1"
    # Agility 60 -> round(6.5) = 6 ticks, y al final del tick ya bajó a 5
    assert h1.cooldown == 5


@pytest.mark.parametrize(
    "player_index, player_x, ball_x, goes_right",
    [
        (0, 15.0, 15.5, True),  # el local patea hacia el arco de la derecha
        (3, 4.0, 3.5, False),  # el visitante patea hacia el arco de la izquierda
    ],
)
def test_shoot_at_goal_aims_at_rival_goal(
    state, rng, player_index, player_x, ball_x, goes_right
):
    player = state.players[player_index]
    player.x, player.y = player_x, 0.0
    state.ball.x, state.ball.y = ball_x, 0.0

    step(state, {player.id: ShootAtGoal()}, rng)

    assert (state.ball.vx > 0) == goes_right
    assert state.ball.vy == pytest.approx(0.0)  # va derecho al centro del arco


def test_pass_reaches_teammate(state, rng):
    h1 = _ball_next_to_h1(state)
    h2 = state.players[1]

    step(state, {h1.id: PassTo(h2.id)}, rng)
    for _ in range(200):  # dejamos que la pelota llegue
        step(state, {}, rng)

    # la pelota queda al alcance de h2 (radio 1.0 con Control 60)
    assert hypot(state.ball.x - h2.x, state.ball.y - h2.y) <= 1.0


@pytest.mark.parametrize("target_id", ["no-existe", "a1", "h1"])
def test_invalid_pass_does_nothing(state, rng, target_id):
    h1 = _ball_next_to_h1(state)

    step(state, {h1.id: PassTo(target_id)}, rng)  # no tiene que explotar

    assert (state.ball.vx, state.ball.vy) == (0.0, 0.0)
    assert state.ball.last_touch_id is None
    assert h1.cooldown == 0


def test_cannot_kick_out_of_reach(state, rng):
    h1 = state.players[0]
    state.ball.x, state.ball.y = -6.0, 0.0  # a 2 m de h1

    step(state, {h1.id: Shoot(1, 0, 100)}, rng)

    assert (state.ball.vx, state.ball.vy) == (0.0, 0.0)


def test_cannot_kick_during_cooldown(state, rng):
    h1 = _ball_next_to_h1(state)
    h1.cooldown = 3

    step(state, {h1.id: Shoot(1, 0, 100)}, rng)

    assert (state.ball.vx, state.ball.vy) == (0.0, 0.0)


def test_move_is_not_a_kick(state, rng):
    h1 = _ball_next_to_h1(state)

    step(state, {h1.id: Move(1, 0, 100)}, rng)

    assert (state.ball.vx, state.ball.vy) == (0.0, 0.0)


def test_strongest_player_wins_the_kick(state, rng):
    # dos rivales con la pelota en su radio
    strong = make_player("h1", Side.HOME, -4.0, 0.0, strength=80, power=40)
    weak = make_player("a1", Side.AWAY, -5.0, 0.0, strength=40, power=80)
    state.players[0], state.players[3] = strong, weak
    state.ball.x, state.ball.y = -4.5, 0.0

    step(state, {"h1": Shoot(1, 0, 100), "a1": Shoot(-1, 0, 100)}, rng)

    assert state.ball.last_touch_id == "h1"
    assert state.ball.vx > 0  # salió para el lado que pateó el fuerte
    assert weak.cooldown == 0  # al perdedor se le anula la patada


def test_strength_tie_is_random(state):
    # mismo Strength: según la semilla tiene que poder ganar cualquiera de los dos
    actions = {"h1": Shoot(1, 0, 100), "a1": Shoot(-1, 0, 100)}
    winners = set()
    for seed in range(20):
        state.players[3].x, state.players[3].y = -5.0, 0.0
        ball = state.ball
        ball.x, ball.y, ball.vx, ball.vy = -4.5, 0.0, 0.0, 0.0
        ball.last_touch_id = None
        for player in state.players:
            player.cooldown = 0

        step(state, actions, random.Random(seed))
        winners.add(ball.last_touch_id)

    assert winners == {"h1", "a1"}
