import logging
import multiprocessing
import time
from textwrap import dedent

import pytest

from app.engine.actions import Move
from app.engine.behavior_exec import create_brains, decide_actions
from app.engine.constants import STARTUP_DEADLINE, TICK_DEADLINE
from app.engine.executor import BehaviorExecutor
from app.engine.state import Side
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

HANG_FROM_2ND = """
    calls = 0
    def decide_action():
        global calls
        calls += 1
        while calls >= 2:
            try:
                while True: pass
            except:
                pass
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


async def test_executor_close(state, make_executor):
    executor = make_executor(state, {"h1": dedent(GO_RIGHT)})

    await executor.decide(state)

    executor.close()
    executor.close()  # la segunda no tiene que tirar error

    for worker in executor._workers.values():
        assert worker._proc not in multiprocessing.active_children()
    assert await executor.decide(state) == {}  # cerradoo


async def test_child_process_hang(state, make_executor):
    executor = make_executor(state, {"h1": dedent(HANG_FROM_2ND)})

    assert await executor.decide(state) == {"h1": Move(1.0, 0.0, 100.0)}

    start = time.monotonic()
    assert await executor.decide(state) == {}
    elapsed = time.monotonic() - start
    assert TICK_DEADLINE <= elapsed < STARTUP_DEADLINE
    assert not executor._workers[Side.HOME]._proc.is_alive()  # el padre lo mató

    start = time.monotonic()
    assert await executor.decide(state) == {}
    elapsed = time.monotonic() - start
    assert elapsed <= 0.05  # como ya se murio hace rato responde al toque


async def test_dead_child_process(state, make_executor):
    executor = make_executor(state, {"h1": dedent(GO_RIGHT)})
    proc = executor._workers[Side.HOME]._proc

    proc.kill()
    proc.join()

    assert await executor.decide(state) == {}
    executor.set_behavior("h1", dedent(GO_RIGHT))


async def test_hang_freezes_only_its_team(state, make_executor):
    executor = make_executor(
        state, {"h1": dedent(HANG_FROM_2ND), "a1": dedent(GO_RIGHT)}
    )
    home_right = Move(1.0, 0.0, 100.0)
    away_right = Move(-1.0, 0.0, 100.0)  # se espeja

    assert await executor.decide(state) == {"h1": home_right, "a1": away_right}
    assert await executor.decide(state) == {"a1": away_right}  # h1 colgó a los locales
    assert not executor._workers[Side.HOME]._proc.is_alive()
    assert executor._workers[Side.AWAY]._proc.is_alive()
    assert await executor.decide(state) == {"a1": away_right}  # los visitantes siguen
