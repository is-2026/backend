import random

import pytest

from app.engine.actions import Move
from app.engine.constants import (
    GOAL_HALF_WIDTH,
    GOALIE_CORRECTION_SPEED_PCT,
    GOALIE_FORMATION,
    KICKER_FORMATION,
    MAX_PENALTIES,
    PENALTY_TICKS,
)
from app.engine.engine import step
from app.engine.penalties import Goalie, Shootout, kick_stopped, penalty_state
from app.engine.state import Side
from tests.engine.conftest import brain_with_snapshot, make_player


def _other_side(side):
    return Side.AWAY if side == Side.HOME else Side.HOME


def _penalty(kicker_side, **pacss):
    kicker = make_player("kicker", kicker_side, **pacss)
    goalie = make_player("goalie", _other_side(kicker_side))
    return penalty_state("home-club", "away-club", kicker, goalie)


def _find(state, player_id):
    return next(p for p in state.players if p.id == player_id)


# --- penalty_state ---
@pytest.mark.parametrize(
    "kicker_side, kicker_x, goalie_x",
    [
        # el local ataca hacia +x: patea desde atrás de la pelota y el arquero
        # visitante defiende el arco de la derecha
        (Side.HOME, KICKER_FORMATION[0][0], -GOALIE_FORMATION[0][0]),
        # el visitante es el espejo
        (Side.AWAY, -KICKER_FORMATION[0][0], GOALIE_FORMATION[0][0]),
    ],
)
def test_penalty_state_positions(kicker_side, kicker_x, goalie_x):
    state = _penalty(kicker_side)
    kicker = _find(state, "kicker")
    goalie = _find(state, "goalie")

    assert (kicker.x, kicker.y) == pytest.approx((kicker_x, 0.0))
    assert (goalie.x, goalie.y) == pytest.approx((goalie_x, 0.0))
    assert (state.ball.x, state.ball.y) == pytest.approx((0.0, 0.0))


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_penalty_state_kicker_view(kicker_side):
    # control 20 es el radio de control más chico, el peor caso para has_ball
    state = _penalty(kicker_side, control=20, power=100)
    brain = brain_with_snapshot(state, "kicker")

    assert brain.has_ball()
    assert brain.team_pos() == []
    assert [rival_id for rival_id, _, _ in brain.enemy_pos()] == ["goalie"]
    assert brain.time() == 0
    assert brain.total_time() == PENALTY_TICKS


def test_penalty_state_score_is_penalty_shootout_score():
    kicker = make_player("kicker", Side.HOME)
    goalie = make_player("goalie", Side.AWAY)
    state = penalty_state(
        "home-club",
        "away-club",
        kicker,
        goalie,
        home_penalties=3,
        away_penalties=2,
    )

    # cada uno ve el marcador de la tanda desde su lado
    assert brain_with_snapshot(state, "kicker").score() == (3, 2)
    assert brain_with_snapshot(state, "goalie").score() == (2, 3)


# --- kick_stopped ---
def _toward_goal(kicker_side, x):
    """Pasa una x vista desde el pateador (ataca hacia +x) a la x absoluta."""
    return x if kicker_side == Side.HOME else -x


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_kick_stopped_fresh_state(kicker_side):
    # la pelota arranca justo en la mitad, no cuenta como despeje
    state = _penalty(kicker_side)
    assert not kick_stopped(state, _find(state, "goalie"))


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_kick_stopped_goalie_touched_ball(kicker_side):
    state = _penalty(kicker_side)
    state.ball.last_touch_id = "goalie"
    assert kick_stopped(state, _find(state, "goalie"))


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_kick_stopped_kicker_attacking(kicker_side):
    # el pateador la llevó hacia el arco, el penal sigue
    state = _penalty(kicker_side)
    state.ball.last_touch_id = "kicker"
    state.ball.x = _toward_goal(kicker_side, 8.0)
    assert not kick_stopped(state, _find(state, "goalie"))


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_kick_stopped_ball_back_in_kicker_half(kicker_side):
    state = _penalty(kicker_side)
    state.ball.last_touch_id = "kicker"
    state.ball.x = _toward_goal(kicker_side, -1.0)
    assert kick_stopped(state, _find(state, "goalie"))


@pytest.mark.parametrize(
    "tick, expected", [(PENALTY_TICKS - 1, False), (PENALTY_TICKS, True)]
)
def test_kick_stopped_time_up(tick, expected):
    state = _penalty(Side.HOME)
    state.tick = tick
    assert kick_stopped(state, _find(state, "goalie")) == expected


# --- Shootout ---
def _shootout(seed=0):
    home = [make_player(f"h{i}", Side.HOME) for i in range(5)]
    away = [make_player(f"a{i}", Side.AWAY) for i in range(5)]
    return Shootout(home, away, random.Random(seed))


def _record_all(shootout, results):
    """Anota los resultados en orden (local, visitante, local, ...)."""
    for scored in results:
        shootout.next_kick()
        shootout.record(scored)


def _ids(kick):
    side, kicker, goalie = kick
    return side, kicker.id, goalie.id


def test_shootout_order_alternates_and_goalie_is_rival_with_same_number():
    shootout = _shootout()
    kicks = []
    for _ in range(10):  # todos errados: nadie se escapa en los primeros 5
        kicks.append(_ids(shootout.next_kick()))
        shootout.record(False)

    assert kicks == [
        (Side.HOME, "h0", "a0"),
        (Side.AWAY, "a0", "h0"),
        (Side.HOME, "h1", "a1"),
        (Side.AWAY, "a1", "h1"),
        (Side.HOME, "h2", "a2"),
        (Side.AWAY, "a2", "h2"),
        (Side.HOME, "h3", "a3"),
        (Side.AWAY, "a3", "h3"),
        (Side.HOME, "h4", "a4"),
        (Side.AWAY, "a4", "h4"),
    ]


def test_shootout_sudden_death_repeats_order_from_first():
    shootout = _shootout()
    _record_all(shootout, [False] * 10)

    assert _ids(shootout.next_kick()) == (Side.HOME, "h0", "a0")
    shootout.record(False)
    assert _ids(shootout.next_kick()) == (Side.AWAY, "a0", "h0")


@pytest.mark.parametrize(
    "results, winner, home_penalties, away_penalties",
    [
        # 3-0 después de 3 por lado (el ejemplo del ticket)
        ([True, False, True, False, True, False], Side.HOME, 3, 0),
        ([False, True, False, True, False, True], Side.AWAY, 0, 3),
        # termina en la mitad de un par: 4-1 con 4 contra 3, el visitante no llega
        ([True, True, True, False, True, False, True], Side.HOME, 4, 1),
        # el local erra el 4to y con 1-3 ya no llega
        ([False, True, False, True, True, True, False], Side.AWAY, 1, 3),
        # se define en el último par de los 5
        ([True, True] * 3 + [True, False, False, False], Side.HOME, 4, 3),
    ],
)
def test_shootout_ends_as_soon_as_result_is_decided(
    results, winner, home_penalties, away_penalties
):
    shootout = _shootout()
    _record_all(shootout, results[:-1])
    assert not shootout.finished  # un penal antes todavía no estaba definido

    _record_all(shootout, results[-1:])
    assert shootout.finished
    assert shootout.winner == winner
    assert (shootout.home_penalties, shootout.away_penalties) == (
        home_penalties,
        away_penalties,
    )


@pytest.mark.parametrize(
    "sudden_death, winner",
    [
        ([True, False], Side.HOME),
        ([False, True], Side.AWAY),
        # pares empatados no definen
        ([True, True, False, False, True, False], Side.HOME),
    ],
)
def test_shootout_sudden_death_ends_on_first_uneven_pair(sudden_death, winner):
    shootout = _shootout()
    _record_all(shootout, [True] * 10 + sudden_death[:-1])
    # aunque convierta el local, el visitante todavía puede empatar
    assert not shootout.finished

    _record_all(shootout, sudden_death[-1:])
    assert shootout.finished
    assert shootout.winner == winner


def test_shootout_draw_after_max_penalties():
    shootout = _shootout(7)
    _record_all(shootout, [True] * (MAX_PENALTIES - 1))
    assert not shootout.finished

    _record_all(shootout, [True])
    assert shootout.finished
    assert shootout.winner in (Side.HOME, Side.AWAY)
    assert (shootout.home_penalties, shootout.away_penalties) == (10, 10)


def test_shootout_record_after_finished_changes_nothing():
    shootout = _shootout()
    _record_all(shootout, [True, False, True, False, True, False])

    shootout.record(True)
    assert shootout.winner == Side.HOME
    assert (shootout.home_penalties, shootout.away_penalties) == (3, 0)


# --- Goalie ---
def _goalie(kicker_side):
    state = _penalty(kicker_side)
    keeper = _find(state, "goalie")
    return state, keeper, Goalie(keeper, random.Random(0))


def test_goalie_waits_for_the_shot():
    state, _, goalie = _goalie(Side.HOME)

    assert goalie.action(state) == Move(0.0, 0.0, 0)


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_goalie_dives_to_a_post_after_the_shot(kicker_side):
    state, keeper, goalie = _goalie(kicker_side)
    post = random.Random(0).choice((-GOAL_HALF_WIDTH, GOAL_HALF_WIDTH))
    state.ball.last_touch_id = "kicker"  # ya remató; la pelota sigue lejos

    action = goalie.action(state)

    assert (action.dx, action.dy, action.speed_pct) == pytest.approx((0.0, post, 100))



def test_goalie_stays_still_once_it_reaches_the_post():
    state, keeper, goalie = _goalie(Side.HOME)
    keeper.y = random.Random(0).choice((-GOAL_HALF_WIDTH, GOAL_HALF_WIDTH))  # ya está en el palo
    state.ball.last_touch_id = "kicker"

    assert goalie.action(state) == Move(0.0, 0.0, 0)

@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_goalie_corrects_toward_the_ball_when_it_gets_close(kicker_side):
    state, keeper, goalie = _goalie(kicker_side)
    state.ball.last_touch_id = "kicker"
    # a 2 m adelante del arquero y corrida 1.5 m: cerca, pero fuera de su radio
    toward_kicker = -1 if keeper.x > 0 else 1
    state.ball.x, state.ball.y = keeper.x + 2.0 * toward_kicker, -1.5

    action = goalie.action(state)

    assert (action.dy, action.speed_pct) == pytest.approx((-1.5, GOALIE_CORRECTION_SPEED_PCT))


@pytest.mark.parametrize("kicker_side", [Side.HOME, Side.AWAY])
def test_goalie_clears_the_ball_when_it_reaches_it(kicker_side):
    state, keeper, goalie = _goalie(kicker_side)
    state.ball.x, state.ball.y = keeper.x, keeper.y  # la pelota le llega

    step(state, {"goalie": goalie.action(state)}, random.Random(0))

    assert kick_stopped(state, keeper)
