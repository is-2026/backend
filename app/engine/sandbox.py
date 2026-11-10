import multiprocessing
import os
import resource
import signal
from contextlib import contextmanager
from multiprocessing.connection import Connection
from multiprocessing.context import SpawnProcess

from app.engine.actions import Action
from app.engine.behavior_exec import (
    CoachBrain,
    CoachSnapshot,
    PlayerBrain,
    Snapshot,
    load_brain,
    load_coach_brain,
)
from app.engine.coach_orders import CoachOrder
from app.engine.constants import (
    CALL_TIMEOUT,
    CODE_LOAD_TIMEOUT,
    MAX_CONSECUTIVE_TIMEOUTS,
    MEMORY_LIMIT_MB,
)
from app.engine.state import PlayerState, Side


@contextmanager
def _time_limit(seconds: float):
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


class BehaviorTimeout(BaseException):
    """El comportamiento excedió el tiempo de ejecución"""


def _behavior_timeout(signum, frame):
    raise BehaviorTimeout("Tiempo de ejecución agotado")


def _load_brain_with_time_limit(
    player: PlayerState, code: str, timeout_seconds: float
) -> PlayerBrain | None:
    try:
        with _time_limit(timeout_seconds):
            return load_brain(player, code)
    except BehaviorTimeout:
        return None


def _load_coach_with_time_limit(
    side: Side, code: str, timeout_seconds: float
) -> CoachBrain | None:  ## carga el codigo del comportamiento de dt, si se cuelga devuelve None
    try:
        with _time_limit(timeout_seconds):
            return load_coach_brain(side, code)
    except BehaviorTimeout:
        return None


def _worker_main(
    conn,
    players: list[PlayerState],
    codes: dict[str, str],
    coach_code: str | None = None,
):
    """
    Tipos de mensajes:
    ("close"),
    ("set", player, code),
    ("decide", snapshot, player_ids, coach_snapshot) -> (acciones, órdenes del DT)
    ("coach", coach_snapshot) -> órdenes del DT (para la llamada de penales)
    coach_snapshot puede ser None: en ese caso no corre el DT.
    Todo esto se lo manda el padre.
    """
    os.environ.clear()
    resource.setrlimit(
        resource.RLIMIT_AS, (MEMORY_LIMIT_MB * 2**20, MEMORY_LIMIT_MB * 2**20)
    )
    signal.signal(signal.SIGALRM, _behavior_timeout)
    brains: dict[str, PlayerBrain] = {}
    timeouts: dict[str, int] = {}  # timeouts: id -> timeouts seguidos
    for player in players:
        code = codes.get(player.id)
        if code is None:
            continue
        brain = _load_brain_with_time_limit(player, code, CODE_LOAD_TIMEOUT)
        if brain is not None:
            timeouts[player.id] = 0
            brains[player.id] = brain

    coach: CoachBrain | None = None
    if coach_code is not None and players:
        # si el código del DT se cuelga al cargar, el equipo juega sin DT
        coach = _load_coach_with_time_limit(
            players[0].side, coach_code, CODE_LOAD_TIMEOUT
        )

    try:
        while True:
            data = conn.recv()
            type_msg = data[0]
            if type_msg == "close":
                break
            elif type_msg == "set":
                _, player, code = data
                brain = _load_brain_with_time_limit(player, code, CODE_LOAD_TIMEOUT)
                if brain is not None:
                    brains[player.id] = brain
                    timeouts[player.id] = 0  # le reincio los timeouts
                # si el código nuevo se cuelga al cargar, sigue con el brain viejo
            elif type_msg == "decide":
                _, snapshot, player_ids, coach_snapshot = data
                # primero los jugadores y después el DT
                actions = _decide_all(brains, timeouts, snapshot, player_ids)
                orders, coach = _decide_coach(coach, coach_snapshot)
                conn.send((actions, orders))
            elif type_msg == "coach":
                _, coach_snapshot = data
                orders, coach = _decide_coach(coach, coach_snapshot)
                conn.send(orders)
    finally:
        conn.close()


def _decide_all(
    brains: dict[str, PlayerBrain],
    timeouts: dict[str, int],
    snapshot: Snapshot,
    player_ids: list[str],
) -> dict[str, Action]:
    actions = {}
    for player_id in player_ids:
        brain = brains.get(player_id)
        if brain is None:
            continue

        try:
            with _time_limit(CALL_TIMEOUT):
                action = brain.run(snapshot)
        except BehaviorTimeout:
            timeouts[player_id] += 1
            if timeouts[player_id] >= MAX_CONSECUTIVE_TIMEOUTS:
                del brains[player_id]
            continue
        except MemoryError:
            del brains[player_id]
            continue

        timeouts[player_id] = 0  # le fue bien,  se reinicia
        if action is not None:
            actions[player_id] = action
    return actions


def _decide_coach(
    coach: CoachBrain | None, snapshot: CoachSnapshot | None
) -> tuple[list[CoachOrder], CoachBrain | None]:
    # al DT no lo saco por timeouts como a los jugadores, solo si se queda sin memoria
    if coach is None or snapshot is None: ## Si alguno es none, no hace nada
        return [], coach
    try:
        with _time_limit(CALL_TIMEOUT):
            orders = coach.run(snapshot)
    except BehaviorTimeout: 
        return [], coach
    except MemoryError:
        return [], None
    return orders, coach


def start_worker(
    players: list[PlayerState], codes: dict[str, str], coach_code: str | None = None
) -> tuple[SpawnProcess, Connection]:
    """Devuelve (proceso, conn_padre)"""
    ctx = multiprocessing.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe()
    proc = ctx.Process( #crea el proceso hijo donde se van a correr  los comportamientos.
        target=_worker_main,
        args=(child_conn, players, codes, coach_code),
        daemon=True,
    )
    proc.start()
    # el padre nunca va a usar este fd, el hijo tiene una copia propia, lo cierro
    child_conn.close()
    return proc, parent_conn
