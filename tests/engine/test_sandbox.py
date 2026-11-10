import multiprocessing
import signal
from textwrap import dedent
from unittest.mock import Mock

import pytest

from app.engine.behavior_exec import CoachSnapshot, load_brain, take_snapshot
from app.engine.coach_orders import SetBehavior
from app.engine.constants import CODE_LOAD_TIMEOUT
from app.engine.sandbox import (
    _behavior_timeout,
    _decide_all,
    _decide_coach,
    _load_brain_with_time_limit,
    start_worker,
)
from app.engine.state import Side

# --- comportamientos de prueba ---

GO_RIGHT = """
    def decide_action():
        move(1, 0, 100)
"""

HANG = """
    def decide_action():
        while True:
            pass
"""

# se cuelga las primeras 3 llamadas y después se mueve
HANG_FIRST_3 = """
    calls = 0
    def decide_action():
        global calls
        calls += 1
        if calls <= 3:
            while True:
                pass
        move(1, 0, 100)
"""

# se cuelga en todas menos la 3ra: nunca llega a 3 timeouts seguidos
HANG_ALL_BUT_3RD = """
    calls = 0
    def decide_action():
        global calls
        calls += 1
        if calls != 3:
            while True:
                pass
        move(1, 0, 100)
"""

# falla en las llamadas impares
FAIL_ON_ODD = """
    calls = 0
    def decide_action():
        global calls
        calls += 1
        if calls % 2 == 1:
            1 / 0
        move(1, 0, 100)
"""

MODULE_HANG = """
    while True:
        pass
    def decide_action():
        move(1, 0, 100)
"""

# ¡solo en el hijo! sin setrlimit, Linux le da los 8 GB a pytest
MEMORY_BOMB = """
    def decide_action():
        x = [0] * 10**9
        move(1, 0, 100)
"""


# --- auxiliares ---


@pytest.fixture
def alarm_handler():
    """_decide_all usa la alarma, pero el handler lo registra _worker_main.
    Llamándola directo lo registro acá sin handler, SIGALRM mata a pytest."""
    previous = signal.signal(signal.SIGALRM, _behavior_timeout)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous)


def home(state):
    return [player for player in state.players if player.side == Side.HOME]


def prepare(state, codes):
    """Arma lo que recibe _decide_all, igual que lo tiene el hijo."""
    brains = {}
    for player in home(state):
        if player.id in codes:
            brains[player.id] = load_brain(player, dedent(codes[player.id]))
    timeouts = {player_id: 0 for player_id in brains}
    snapshot = take_snapshot(state, Side.HOME)
    player_ids = [player.id for player in home(state)]
    return brains, timeouts, snapshot, player_ids


def everyone(state, code, **overrides):
    """Todos con el mismo código, salvo los que se pisan: everyone(state, X, h1=Y)"""
    codes = {player.id: code for player in state.players}
    codes.update(overrides)
    return codes


@pytest.fixture
def spawn_worker():
    """Levanta workers de verdad y, pase lo que pase en el test, los cierra."""
    started = []

    def spawn(players, codes, coach_code=None):
        proc, conn = start_worker(
            players,
            {k: dedent(v) for k, v in codes.items()},
            dedent(coach_code) if coach_code is not None else None,
        )
        started.append((proc, conn))
        return proc, conn

    yield spawn

    for proc, conn in started:
        try:
            conn.send(("close",))
        except OSError:  # el hijo ya murió o el test cerró el caño
            pass
        proc.join(2)
        if proc.is_alive():
            proc.kill()
            proc.join()
        conn.close()


def ask(conn, state, timeout=5.0):
    """Pide un decide al hijo (sin DT) y devuelve solo las acciones.
    timeout largo: el primero incluye el arranque."""
    snapshot = take_snapshot(state, Side.HOME)
    conn.send(("decide", snapshot, [player.id for player in home(state)], None))
    assert conn.poll(timeout), "el hijo no contestó"
    actions, _ = conn.recv()
    return actions


# --- _decide_all directo ---


def test_hanging_player_gets_no_action_and_the_rest_play(state, alarm_handler):
    brains, timeouts, snapshot, on_field = prepare(
        state, everyone(state, GO_RIGHT, h1=HANG)
    )

    actions = _decide_all(brains, timeouts, snapshot, on_field)

    assert set(actions) == {"h2", "h3"}


def test_deactivate_after_max_timeouts(state, alarm_handler):
    brains, timeouts, snapshot, on_field = prepare(
        state, everyone(state, GO_RIGHT, h1=HANG_FIRST_3)
    )
    for _ in range(3):
        actions = _decide_all(brains, timeouts, snapshot, on_field)

    assert "h1" not in brains

    actions = _decide_all(brains, timeouts, snapshot, on_field)
    assert "h1" not in actions


def test_timeouts_restart(state, alarm_handler):
    brains, timeouts, snapshot, on_field = prepare(
        state, everyone(state, GO_RIGHT, h1=HANG_ALL_BUT_3RD)
    )
    for _ in range(5):
        _decide_all(brains, timeouts, snapshot, on_field)

    assert "h1" in brains


def test_deactivate_behavior_mem_limit(state, alarm_handler):
    brains, timeouts, snapshot, on_field = prepare(state, everyone(state, GO_RIGHT))
    bombita = Mock()
    bombita.run.side_effect = MemoryError
    brains["h1"] = bombita

    actions = _decide_all(brains, timeouts, snapshot, on_field)

    assert "h1" not in brains
    assert "h1" not in actions


def test_no_action_if_exception(state, alarm_handler):
    brains, timeouts, snapshot, on_field = prepare(
        state, everyone(state, GO_RIGHT, h1=FAIL_ON_ODD)
    )

    first = _decide_all(brains, timeouts, snapshot, on_field)
    second = _decide_all(brains, timeouts, snapshot, on_field)

    assert "h1" not in first
    assert "h1" in second


def test_load_brain_hang(state, alarm_handler):
    assert (
        _load_brain_with_time_limit(
            state.players[0], dedent(MODULE_HANG), CODE_LOAD_TIMEOUT
        )
        is None
    )


# --- con el proceso hijo de verdad ---


def test_memory_bomb_leaves_player_still_and_the_rest_play(state, spawn_worker):
    _, conn = spawn_worker(home(state), everyone(state, GO_RIGHT, h1=MEMORY_BOMB))

    assert set(ask(conn, state)) == {"h2", "h3"}
    assert set(ask(conn, state)) == {"h2", "h3"}


def test_worker_close(state, spawn_worker):
    proc, conn = spawn_worker(state.players, everyone(state, GO_RIGHT))
    ask(conn, state)
    conn.send(("close",))
    proc.join(2)
    assert proc.exitcode == 0
    assert multiprocessing.active_children() == []


# --- DT ---

COACH = """
    def decide_coach():
        set_behavior("h1", "b2")
"""

# se cuelga en la primera llamada y despues da la orden
COACH_HANG_FIRST = """
    calls = 0
    def decide_coach():
        global calls
        calls += 1
        if calls == 1:
            while True:
                pass
        set_behavior("h1", "b2")
"""



def coach_snapshot():
    return CoachSnapshot(
        own_score=0,
        rival_score=0,
        tick=10,
        total_ticks=3000,
        on_field=(("h1", "b1"), ("h2", "b1"), ("h3", "b1")),
        bench=("h4", "h5", "h6"),
        behaviors=(("b1", "Atacante"), ("b2", "Defensor")),
        penalty_shootout=False,
    )


def ask_with_coach(conn, state, timeout=5.0):
    snapshot = take_snapshot(state, Side.HOME)
    ids = [player.id for player in home(state)]
    conn.send(("decide", snapshot, ids, coach_snapshot()))
    assert conn.poll(timeout), "el hijo no contestó"
    return conn.recv()


def test_coach_out_of_memory_is_removed(alarm_handler):
    bombita = Mock()
    bombita.run.side_effect = MemoryError

    assert _decide_coach(bombita, coach_snapshot()) == ([], None)


def test_worker_returns_actions_and_orders(state, spawn_worker):
    _, conn = spawn_worker(home(state), everyone(state, GO_RIGHT), COACH)

    actions, orders = ask_with_coach(conn, state)

    assert set(actions) == {"h1", "h2", "h3"}
    assert orders == [SetBehavior("h1", "b2")]


def test_hanging_coach_does_not_stop_the_players(state, spawn_worker):
    _, conn = spawn_worker(home(state), everyone(state, GO_RIGHT), COACH_HANG_FIRST)

    actions, orders = ask_with_coach(conn, state)
    assert set(actions) == {"h1", "h2", "h3"}
    assert orders == []

    _, orders = ask_with_coach(conn, state)
    assert orders == [SetBehavior("h1", "b2")]
