from textwrap import dedent

from app.engine.actions import Move
from app.engine.behavior_exec import PlayerBrain, compile_behavior, take_snapshot
from app.engine.state import Side


def make_brain(state, player_id, code="def decide_action():\n    pass\n"):
    player = next(p for p in state.players if p.id == player_id)
    return PlayerBrain(player, compile_behavior(dedent(code), "test"))


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


def test_my_pos_home(state):
    brain = make_brain(state, "h2")
    brain.run(take_snapshot(state, Side.HOME))
    assert brain.my_pos() == (-12.0, -5.0)


def test_my_pos_away(state):
    brain = make_brain(state, "a1")
    brain.run(take_snapshot(state, Side.AWAY))
    assert brain.my_pos() == (-4.0, 0.0)


def test_ball_pos_home(state):
    state.ball.x, state.ball.y = 5.0, 2.0
    brain = make_brain(state, "h1")
    brain.run(take_snapshot(state, Side.HOME))
    assert brain.ball_pos() == (5.0, 2.0)


def test_ball_pos_away(state):
    state.ball.x, state.ball.y = 5.0, 2.0
    brain = make_brain(state, "a1")
    brain.run(take_snapshot(state, Side.AWAY))
    assert brain.ball_pos() == (-5.0, -2.0)


def test_home_move_is_not_rotated(state):
    # h2 está en (-12, -5) y ve la pelota (en el centro) adelante suyo: hacia +x en su vista
    brain = make_brain(
        state,
        "h2",
        """
        def decide_action():
            move(1, 0, 100)
        """,
    )

    action = brain.run(take_snapshot(state, Side.HOME))

    assert action == Move(1.0, 0.0, 100.0)


def test_away_move_is_rotated_to_absolute(state):
    # a1 está en (4, 0) y ve la pelota (en el centro) adelante suyo: hacia +x en su vista
    brain = make_brain(
        state,
        "a1",
        """
        def decide_action():
            move(1, 0, 100)
        """,
    )

    action = brain.run(take_snapshot(state, Side.AWAY))

    assert action == Move(-1.0, 0.0, 100.0)  # en absolutas va hacia -x
