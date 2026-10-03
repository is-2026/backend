import logging
from textwrap import dedent

import pytest

from app.engine.actions import Move, PassTo, Shoot, ShootAtGoal
from app.engine.behavior_exec import (
    InvalidBehaviorCode,
    PlayerBrain,
    compile_behavior,
    create_brains,
    decide_actions,
    take_snapshot,
)
from app.engine.state import Side


# --- auxiliares ---
def make_brain(state, player_id, code="def decide_action():\n    pass\n"):
    player = next(p for p in state.players if p.id == player_id)
    return PlayerBrain(player, compile_behavior(dedent(code), "test"))


def brain_with_snapshot(state, player_id):
    """Brain que ya recibió la foto de su lado, listo para consultar primitivas."""
    player = next(p for p in state.players if p.id == player_id)
    brain = make_brain(state, player_id)
    brain.run(take_snapshot(state, player.side))
    return brain


def run_behavior(state, player_id, code):
    """Corre el comportamiento un tick y devuelve la acción que decidió."""
    player = next(p for p in state.players if p.id == player_id)
    return make_brain(state, player_id, code).run(take_snapshot(state, player.side))


# --- snapshots ---
def test_take_snapshot_home(state):
    state.ball.x, state.ball.y = 5.0, 2.0
    state.home_score, state.away_score = 4, 1
    state.tick = 10

    snapshot = take_snapshot(state, Side.HOME)

    # el local ve todo igual que el estado, absoluto
    assert [(p.id, p.x, p.y) for p in snapshot.teammates] == [
        ("h1", -4, 0),
        ("h2", -12, -5),
        ("h3", -12, 5),
    ]
    assert [(p.id, p.x, p.y) for p in snapshot.rivals] == [
        ("a1", 4, 0),
        ("a2", 12, 5),
        ("a3", 12, -5),
    ]
    assert (snapshot.ball.x, snapshot.ball.y) == (5.0, 2.0)
    assert (snapshot.own_score, snapshot.rival_score) == (4, 1)
    assert (snapshot.tick, snapshot.total_ticks) == (10, 3000)


def test_take_snapshot_away(state):
    state.ball.x, state.ball.y = 5.0, 2.0
    state.home_score, state.away_score = 4, 1
    state.tick = 10

    snapshot = take_snapshot(state, Side.AWAY)

    # el visitante ve todo dado vuelta, relativo
    assert [(p.id, p.x, p.y) for p in snapshot.teammates] == [
        ("a1", -4, 0),
        ("a2", -12, -5),
        ("a3", -12, 5),
    ]
    assert [(p.id, p.x, p.y) for p in snapshot.rivals] == [
        ("h1", 4, 0),
        ("h2", 12, 5),
        ("h3", 12, -5),
    ]
    assert (snapshot.ball.x, snapshot.ball.y) == (-5.0, -2.0)
    assert (snapshot.own_score, snapshot.rival_score) == (1, 4)
    assert (snapshot.tick, snapshot.total_ticks) == (10, 3000)


# --- primitivas de lectura ---
def test_my_pos_home(state):
    brain = brain_with_snapshot(state, "h2")
    assert brain.my_pos() == (-12.0, -5.0)


def test_my_pos_away(state):
    brain = brain_with_snapshot(state, "a1")
    assert brain.my_pos() == (-4.0, 0.0)


def test_ball_pos_home(state):
    state.ball.x, state.ball.y = 5.0, 2.0
    brain = brain_with_snapshot(state, "h1")
    assert brain.ball_pos() == (5.0, 2.0)


def test_ball_pos_away(state):
    state.ball.x, state.ball.y = 5.0, 2.0
    brain = brain_with_snapshot(state, "a1")
    assert brain.ball_pos() == (-5.0, -2.0)


# Control 60 -> radio 1.0 m. h1 está en (-4, 0)
@pytest.mark.parametrize(
    ("ball_x", "expected"),
    [
        (-4.9, True),  # a 0.9 m
        (-5.0, True),  # justo en el borde, el motor usa <=
        (-5.1, False),  # a 1.1 m
    ],
)
def test_has_ball_home(state, ball_x, expected):
    state.ball.x, state.ball.y = ball_x, 0.0
    brain = brain_with_snapshot(state, "h1")
    assert brain.has_ball() is expected


def test_has_ball_away(state):
    # a1 está en (4, 0) y la pelota a 0.5 m: jugador y pelota se rotan juntos
    state.ball.x, state.ball.y = 4.5, 0.0
    brain = brain_with_snapshot(state, "a1")
    assert brain.has_ball() is True


def test_team_pos_excludes_self(state):
    brain = brain_with_snapshot(state, "h1")
    assert brain.team_pos() == [("h2", -12, -5), ("h3", -12, 5)]


def test_team_pos_away(state):
    brain = brain_with_snapshot(state, "a1")
    assert brain.team_pos() == [("a2", -12, -5), ("a3", -12, 5)]


def test_enemy_pos_home(state):
    brain = brain_with_snapshot(state, "h1")
    assert brain.enemy_pos() == [("a1", 4, 0), ("a2", 12, 5), ("a3", 12, -5)]


def test_enemy_pos_away(state):
    brain = brain_with_snapshot(state, "a1")
    assert brain.enemy_pos() == [("h1", 4, 0), ("h2", 12, 5), ("h3", 12, -5)]


@pytest.mark.parametrize(
    ("player_id", "expected"),
    [
        ("h1", (4, 1)),
        ("a1", (1, 4)),  # (propios, rival)
    ],
)
def test_score(state, player_id, expected):
    state.home_score, state.away_score = 4, 1
    brain = brain_with_snapshot(state, player_id)
    assert brain.score() == expected


def test_time_and_total_time(state):
    state.tick = 10
    brain = brain_with_snapshot(state, "a1")
    assert brain.time() == 10
    assert brain.total_time() == 3000


# --- primitivas de acción ---
def test_home_move_is_not_rotated(state):
    # h2 está en (-12, -5) y ve la pelota (en el centro) adelante suyo: hacia +x en su vista
    code = """
        def decide_action():
            move(1, 0, 100)
    """
    action = run_behavior(state, "h2", code)

    assert action == Move(1.0, 0.0, 100.0)


def test_away_move_is_rotated_to_absolute(state):
    # a1 está en (4, 0) y ve la pelota (en el centro) adelante suyo: hacia +x en su vista
    code = """
        def decide_action():
            move(1, 0, 100)
    """
    action = run_behavior(state, "a1", code)

    assert action == Move(-1.0, 0.0, 100.0)  # en absolutas va hacia -x


@pytest.mark.parametrize("bad", ["float('nan')", "float('inf')", "float('-inf')"])
def test_move_rejects_non_finite(state, bad):
    action = run_behavior(
        state, "h1", f"def decide_action():\n    move({bad}, 0, 100)\n"
    )
    assert action is None


def test_home_shoot_is_not_rotated(state):
    code = """
        def decide_action():
            shoot(10, 5, 100)
    """
    action = run_behavior(state, "h2", code)

    assert action == Shoot(10.0, 5.0, 100.0)


def test_away_shoot_is_rotated(state):
    code = """
        def decide_action():
            shoot(10, 5, 100)
    """
    action = run_behavior(state, "a1", code)

    assert action == Shoot(-10.0, -5.0, 100.0)


@pytest.mark.parametrize("bad", ["float('nan')", "float('inf')", "float('-inf')"])
def test_shoot_rejects_non_finite(state, bad):
    action = run_behavior(
        state, "h1", f"def decide_action():\n    shoot({bad}, 0, 100)\n"
    )
    assert action is None


def test_shoot_arco(state):
    code = """
        def decide_action():
            shoot_arco()
        """
    action = run_behavior(state, "a1", code)

    assert action == ShootAtGoal()


def test_pass_to(state):
    code = """
        def decide_action():
            pass_to("h2")
    """
    action = run_behavior(state, "h1", code)

    assert action == PassTo("h2")


def test_second_action_is_ignored(state):
    code = """
        def decide_action():
            move(1, 0, 100)
            shoot(1, 0, 100)
    """
    action = run_behavior(state, "h1", code)

    assert action == Move(1.0, 0.0, 100.0)


def test_action_resets_between_ticks(state):
    code = """
        n = 0
        def decide_action():
            global n
            n += 1
            if n == 1:
                move(1, 0, 100)
            if n == 2:
                shoot(1, 0, 100)
    """
    brain = make_brain(state, "h1", code)
    snapshot = take_snapshot(state, Side.HOME)

    assert brain.run(snapshot) == Move(1.0, 0.0, 100)
    state.tick += 1

    snapshot = take_snapshot(state, Side.HOME)

    assert brain.run(snapshot) == Shoot(1, 0, 100)
    state.tick += 1

    snapshot = take_snapshot(state, Side.HOME)

    assert brain.run(snapshot) is None


# --- errores en el código del comportamiento ---
def test_exception_in_decide_action_is_logged(state, caplog):
    action = run_behavior(
        state,
        "h1",
        """
        def decide_action():
            1 / 0
        """,
    )

    assert action is None
    assert "h1" in caplog.text  # el log dice qué jugador falló
    assert "ZeroDivisionError" in caplog.text  # y por qué


def test_action_before_exception_is_discarded(state):
    action = run_behavior(
        state,
        "h1",
        """
        def decide_action():
            move(1, 0, 100)
            raise ValueError("falla después de moverse")
        """,
    )

    assert action is None


def test_invalid_argument_is_logged(state, caplog):
    action = run_behavior(
        state,
        "h1",
        """
        def decide_action():
            shoot("hola", 0, 100)
        """,
    )

    assert action is None
    assert "ValueError" in caplog.text


def test_decide_action_not_callable(state):
    action = run_behavior(state, "h1", "decide_action = 5\n")

    assert action is None


def test_player_recovers_after_failing_tick(state):
    # el error solo le hace perder ESE tick, no queda deshabilitado
    brain = make_brain(
        state,
        "h1",
        """
        n = 0
        def decide_action():
            global n
            n += 1
            if n == 1:
                raise ValueError("falla solo en el primer tick")
            move(1, 0, 100)
        """,
    )
    snapshot = take_snapshot(state, Side.HOME)

    assert brain.run(snapshot) is None
    assert brain.run(snapshot) == Move(1.0, 0.0, 100.0)


# --- errores al cargar el código ---
def test_load_error_disables_player(state, caplog):
    brain = make_brain(
        state,
        "h1",
        """
        1 / 0  # falla a nivel módulo, antes de definir decide_action
        def decide_action():
            move(1, 0, 100)
        """,
    )
    snapshot = take_snapshot(state, Side.HOME)

    assert "h1" in caplog.text
    # queda deshabilitado todo el partido, no solo un tick
    assert brain.run(snapshot) is None
    assert brain.run(snapshot) is None


def test_load_error_after_defining_decide_action_disables_player(state):
    # aunque decide_action llegó a definirse, el código no cargó entero: no juega
    brain = make_brain(
        state,
        "h1",
        """
        def decide_action():
            move(1, 0, 100)
        1 / 0
        """,
    )

    assert brain.run(take_snapshot(state, Side.HOME)) is None


def test_missing_decide_action_logs_warning(state, caplog):
    # como los defaults placeholder que quedaron guardados en la base
    make_brain(
        state,
        "h1",
        """
        def decidir_accion():
            pass
        """,
    )

    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_syntax_error_raises_invalid_behavior_code():
    with pytest.raises(InvalidBehaviorCode):
        compile_behavior("def decide_action(:\n", "roto")


# --- decide_actions()
CHASE_BALL = """
    def decide_action():
        x, y = my_pos()
        bx, by = ball_pos()
        move(bx - x, by - y, 100)
"""

BROKEN = """
    def decide_action():
        1 / 0
"""


def same_code_for_all(state, code):
    """codes para create_brains: todos los jugadores con el mismo comportamiento."""
    return {p.id: dedent(code) for p in state.players}


def test_each_player_sees_its_own_side(state):
    # mismo código en los 6. Si cada uno lee la foto de su lado y su acción se
    # rota de vuelta, todos terminan yendo hacia la pelota en absolutas
    state.ball.x, state.ball.y = 5.0, 2.0
    brains = create_brains(state, same_code_for_all(state, CHASE_BALL))

    actions = decide_actions(state, brains)

    assert actions == {
        "h1": Move(9.0, 2.0, 100.0),  # h1 en (-4, 0)
        "h2": Move(17.0, 7.0, 100.0),  # h2 en (-12, -5)
        "h3": Move(17.0, -3.0, 100.0),  # h3 en (-12, 5)
        "a1": Move(1.0, 2.0, 100.0),  # a1 en (4, 0)
        "a2": Move(-7.0, -3.0, 100.0),  # a2 en (12, 5)
        "a3": Move(-7.0, 7.0, 100.0),  # a3 en (12, -5)
    }


def test_broken_player_does_not_stop_the_rest(state):
    codes = same_code_for_all(state, CHASE_BALL)
    codes["h2"] = dedent(BROKEN)
    brains = create_brains(state, codes)

    actions = decide_actions(state, brains)

    assert set(actions) == {"h1", "h3", "a1", "a2", "a3"}
