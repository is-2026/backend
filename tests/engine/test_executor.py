import logging
from textwrap import dedent

from app.engine.actions import Move
from app.engine.behavior_exec import create_brains, decide_actions
from app.engine.executor import BehaviorExecutor
from tests.engine.conftest import same_code_for_all

CHASE_BALL = """
    def decide_action():
        x, y = my_pos()
        bx, by = ball_pos()
        move(bx - x, by - y, 100)
"""

GO_RIGHT = """
    def decide_action():
        move(1, 0, 100)
"""


async def test_decide_matches_decide_actions(state):
    codes = same_code_for_all(state, CHASE_BALL)
    executor = BehaviorExecutor(state, codes)

    actions = await executor.decide(state)

    assert actions == decide_actions(state, create_brains(state, codes))


async def test_set_behavior_changes_only_that_player(state):
    executor = BehaviorExecutor(state, same_code_for_all(state, CHASE_BALL))
    before = await executor.decide(state)

    executor.set_behavior("h1", dedent(GO_RIGHT))
    after = await executor.decide(state)

    assert after["h1"] == Move(1.0, 0.0, 100.0)
    assert {k: v for k, v in after.items() if k != "h1"} == {
        k: v for k, v in before.items() if k != "h1"
    }


async def test_set_behavior_with_invalid_code_keeps_the_old_one(state, caplog):
    executor = BehaviorExecutor(state, {"h1": dedent(GO_RIGHT)})

    with caplog.at_level(logging.ERROR):
        executor.set_behavior("h1", "def decide_action(:\n")

    assert await executor.decide(state) == {"h1": Move(1.0, 0.0, 100.0)}
    assert "no compila" in caplog.text


async def test_set_behavior_of_unknown_player_does_nothing(state, caplog):
    executor = BehaviorExecutor(state, {"h1": dedent(GO_RIGHT)})

    with caplog.at_level(logging.WARNING):
        executor.set_behavior("jugador inexistente", dedent(CHASE_BALL))

    assert await executor.decide(state) == {"h1": Move(1.0, 0.0, 100.0)}
    assert "No existe el jugador jugador inexistente" in caplog.text
