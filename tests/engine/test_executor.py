import logging
from textwrap import dedent

import pytest

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


@pytest.fixture
def make_executor():
    """Hace executors, al final le hace close() a cada uno"""
    started = []

    def make(state, codes):
        executor = BehaviorExecutor(state, codes)
        started.append(executor)
        return executor

    yield make

    for executor in started:
        executor.close()


async def test_decide_matches_decide_actions(state, make_executor):
    codes = same_code_for_all(state, CHASE_BALL)
    executor = make_executor(state, codes)

    actions = await executor.decide(state)

    assert actions == decide_actions(state, create_brains(state, codes))


async def test_set_behavior_changes_only_that_player(state, make_executor):
    executor = make_executor(state, same_code_for_all(state, CHASE_BALL))
    before = await executor.decide(state)

    executor.set_behavior("h1", dedent(GO_RIGHT))
    after = await executor.decide(state)

    assert after["h1"] == Move(1.0, 0.0, 100.0)
    assert {k: v for k, v in after.items() if k != "h1"} == {
        k: v for k, v in before.items() if k != "h1"
    }


async def test_set_behavior_with_invalid_code_keeps_the_old_one(state, make_executor):
    executor = make_executor(state, {"h1": dedent(GO_RIGHT)})

    executor.set_behavior("h1", "def decide_action(:\n")

    assert await executor.decide(state) == {"h1": Move(1.0, 0.0, 100.0)}


async def test_set_behavior_of_unknown_player_does_nothing(
    state, caplog, make_executor
):
    executor = make_executor(state, {"h1": dedent(GO_RIGHT)})

    with caplog.at_level(logging.WARNING):
        executor.set_behavior("jugador inexistente", dedent(CHASE_BALL))

    assert await executor.decide(state) == {"h1": Move(1.0, 0.0, 100.0)}
    assert "No existe el jugador jugador inexistente" in caplog.text
