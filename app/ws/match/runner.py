import asyncio
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from app.engine.constants import DT
from app.engine.engine import kickoff, step
from app.engine.executor import BehaviorExecutor
from app.engine.state import MatchState
from app.ws.connection_manager import ConnectionManager
from app.ws.match.messages import (
    MatchInfo,
    goal_message,
    match_finished_message,
    match_resumed_message,
    match_started_message,
    match_state_message,
    pause_start_message,
)
from app.ws.match.pauses import (
    COOLING_BREAK_SECONDS,
    HALFTIME_SECONDS,
    Pause,
    pauses_schedule,
)

logger = logging.getLogger(__name__)

START_DELAY_SECONDS = 3.0  # tiempo para que los clientes se conecten antes del tick 1


class Phase(StrEnum):
    WAITING = "waiting"
    PLAYING = "playing"
    PAUSED = "paused"
    PENALTIES = "penalties"
    FINISHED = "finished"


@dataclass
class LiveMatch:
    match_id: uuid.UUID
    state: MatchState
    executor: BehaviorExecutor
    # lo fijo de matchStarted (clubes y alineaciones)
    info: MatchInfo
    match_start: datetime  # cuándo termina la espera y empieza a correr el partido
    # fase interna del runner
    phase: Phase = Phase.WAITING
    # último matchState ya serializado, para el que se conecta
    last_state: dict | None = None
    # inicio de la pausa en curso ya serializado para el que se une justo en la pausa
    current_pause: dict | None = None
    # referencia a la tarea, si nadie la guarda, se puede perder
    task: asyncio.Task | None = None


# Partidos que se están jugando ahora. Vive en memoria: con más de un worker no anda.
live_matches: dict[uuid.UUID, LiveMatch] = {}
match_connections = ConnectionManager()


def start_match(
    match_id: uuid.UUID,
    state: MatchState,
    codes: dict[str, str],
    info: MatchInfo,
    *,
    tick_interval: float = DT,
    start_delay: float = START_DELAY_SECONDS,
    cooling_break_duration: float = COOLING_BREAK_SECONDS,
    halftime_duration: float = HALFTIME_SECONDS,
) -> LiveMatch:
    """Prepara el partido, lo anota en live_matches y lo larga como tarea de fondo.
    codes = player_id -> código del comportamiento.
    Es sync pero usa create_task: hay que llamarla dentro del event loop."""
    if match_id in live_matches:
        return live_matches[match_id]  # ya se está jugando: no lo largamos dos veces

    kickoff(state)
    live = LiveMatch(
        match_id=match_id,
        state=state,
        executor=BehaviorExecutor(state, codes),
        info=info,
        match_start=datetime.now(timezone.utc) + timedelta(seconds=start_delay),
    )
    # el que se conecta durante la espera ya ve a los jugadores en formación (tick 0)
    live.last_state = _state_payload(live)
    live_matches[match_id] = live
    live.task = asyncio.create_task(
        run_match(
            live, tick_interval, start_delay, cooling_break_duration, halftime_duration
        )
    )
    return live


async def _pause(live: LiveMatch, pause: Pause, seconds: float) -> None:
    """Avisa la pausa, espera y avisa la reanudación del partido"""
    match_id = str(live.match_id)
    live.current_pause = pause_start_message(
        match_id, live.state, pause, seconds
    ).model_dump(mode="json")
    live.phase = Phase.PAUSED
    await match_connections.broadcast(live.match_id, live.current_pause)

    await asyncio.sleep(seconds)

    if pause == Pause.HALFTIME:
        kickoff(live.state)
    live.phase = Phase.PLAYING
    live.current_pause = None
    resumed = match_resumed_message(match_id, live.state, pause)
    await match_connections.broadcast(live.match_id, resumed.model_dump(mode="json"))


async def run_match(
    live: LiveMatch,
    tick_interval: float = DT,
    start_delay: float = START_DELAY_SECONDS,
    cooling_break_duration: float = COOLING_BREAK_SECONDS,
    halftime_duration: float = HALFTIME_SECONDS,
) -> None:
    """Espera start_delay y juega hasta total_ticks.
    Por tick: decide_actions -> step -> goal(s) -> matchState.
    Si hay una pausa espera y envía los avisos correspondientes.
    Al terminar bien se manda matchFinished, luego lo saca de live_matches
    y cierra las conexiones (también si se cierra mal)."""
    loop = asyncio.get_running_loop()
    rng = random.Random()
    try:
        pause_schedule = pauses_schedule(live.state.total_ticks)
        await asyncio.sleep(start_delay)
        live.phase = Phase.PLAYING
        next_tick = loop.time()
        while live.state.tick < live.state.total_ticks:
            actions = await live.executor.decide(live.state)
            goals = step(live.state, actions, rng)

            for goal in goals:
                message = goal_message(str(live.match_id), goal, live.state)
                await match_connections.broadcast(
                    live.match_id, message.model_dump(mode="json")
                )

            live.last_state = _state_payload(live)
            await match_connections.broadcast(live.match_id, live.last_state)

            pause = pause_schedule.get(live.state.tick)
            if pause is not None:
                pause_duration = (
                    halftime_duration
                    if pause == Pause.HALFTIME
                    else cooling_break_duration
                )
                await _pause(live, pause, pause_duration)
                # el próximo tick se cuenta desde ahora
                next_tick = loop.time()

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
        live.phase = Phase.FINISHED
        live_matches.pop(live.match_id, None)
        await match_connections.close_all(live.match_id)
        live.executor.close()


def _state_payload(live: LiveMatch) -> dict:
    """matchState del estado actual, listo para mandar."""
    return match_state_message(str(live.match_id), live.state).model_dump(mode="json")


def started_payload(live: LiveMatch) -> dict:
    """matchStarted para el que se acaba de conectar, con el tick y marcador de ahora.
    exclude_none: los suplentes no llevan behavior_id/behavior_name (en vez de null)."""
    status = "paused" if live.phase == Phase.PAUSED else "in_progress"
    message = match_started_message(
        str(live.match_id), live.info, live.match_start, live.state, status
    )
    return message.model_dump(mode="json", exclude_none=True)
