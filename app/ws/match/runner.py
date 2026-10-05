import asyncio
import logging
import random
import uuid
from dataclasses import dataclass

from app.engine.behavior_exec import PlayerBrain, create_brains, decide_actions
from app.engine.constants import DT
from app.engine.engine import kickoff, step
from app.engine.state import MatchState
from app.ws.connection_manager import ConnectionManager
from app.ws.match.messages import (
    goal_message,
    match_finished_message,
    match_state_message,
)

logger = logging.getLogger(__name__)

START_DELAY_SECONDS = 3.0  # tiempo para que los clientes se conecten antes del tick 1


@dataclass
class LiveMatch:
    match_id: uuid.UUID
    state: MatchState
    brains: dict[str, PlayerBrain]
    # último matchState ya serializado, para el que se conecta
    last_state: dict | None = None
    # referencia a la tarea, si nadie la guarda, se puede perder
    task: asyncio.Task | None = None


# Partidos que se están jugando ahora. Vive en memoria: con más de un worker no anda.
live_matches: dict[uuid.UUID, LiveMatch] = {}
match_connections = ConnectionManager()


def start_match(
    match_id: uuid.UUID,
    state: MatchState,
    codes: dict[str, str],
    *,
    tick_interval: float = DT,
    start_delay: float = START_DELAY_SECONDS,
) -> LiveMatch:
    """Prepara el partido, lo anota en live_matches y lo larga como tarea de fondo.
    codes = player_id -> código del comportamiento.
    Es sync pero usa create_task: hay que llamarla dentro del event loop."""
    if match_id in live_matches:
        return live_matches[match_id]  # ya se está jugando: no lo largamos dos veces

    kickoff(state)
    live = LiveMatch(match_id=match_id, state=state, brains=create_brains(state, codes))
    # el que se conecta durante la espera ya ve a los jugadores en formación (tick 0)
    live.last_state = _state_payload(live)
    live_matches[match_id] = live
    live.task = asyncio.create_task(run_match(live, tick_interval, start_delay))
    return live


async def run_match(
    live: LiveMatch,
    tick_interval: float = DT,
    start_delay: float = START_DELAY_SECONDS,
) -> None:
    """Espera start_delay y juega hasta total_ticks.
    Por tick: decide_actions -> step -> goal(s) -> matchState.
    Al terminar bien se manda matchFinished, luego lo saca de live_matches
    y cierra las conexiones (también si se cierra mal)."""
    loop = asyncio.get_running_loop()
    rng = random.Random()
    try:
        await asyncio.sleep(start_delay)
        next_tick = loop.time()
        while live.state.tick < live.state.total_ticks:
            actions = decide_actions(live.state, live.brains)
            goals = step(live.state, actions, rng)

            for goal in goals:
                message = goal_message(str(live.match_id), goal, live.state)
                await match_connections.broadcast(
                    live.match_id, message.model_dump(mode="json")
                )

            live.last_state = _state_payload(live)
            await match_connections.broadcast(live.match_id, live.last_state)

            # dormir hasta el próximo tick descontando lo que tardó este,
            # así el partido dura lo que tiene que durar
            next_tick += tick_interval
            await asyncio.sleep(max(0.0, next_tick - loop.time()))

        # cuando se termina de jugar:
        finished = match_finished_message(str(live.match_id), live.state)
        await match_connections.broadcast(
            live.match_id, finished.model_dump(mode="json")
        )
    except Exception:
        logger.exception("El partido %s se cortó por un error", live.match_id)
    finally:
        live_matches.pop(live.match_id, None)
        await match_connections.close_all(live.match_id)


def _state_payload(live: LiveMatch) -> dict:
    """matchState del estado actual, listo para mandar."""
    return match_state_message(str(live.match_id), live.state).model_dump(mode="json")
