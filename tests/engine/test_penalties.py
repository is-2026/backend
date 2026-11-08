import pytest

from app.engine.constants import FIELD_HALF_LENGTH, KICKER_FORMATION, PENALTY_TICKS
from app.engine.events import GoalEvent
from app.engine.penalties import kick_scored, kick_stopped, penalty_state
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
        (Side.HOME, KICKER_FORMATION[0][0], FIELD_HALF_LENGTH),
        # el visitante es el espejo
        (Side.AWAY, -KICKER_FORMATION[0][0], -FIELD_HALF_LENGTH),
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


# --- kick_scored ---
def test_kick_scored_without_goal():
    assert not kick_scored([])


def test_kick_scored_with_goal():
    goal = GoalEvent(tick=30, player_id="kicker", team_id="home-club", minute=0)
    assert kick_scored([goal])


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
