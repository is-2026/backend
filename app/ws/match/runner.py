import asyncio
import logging
import random
import uuid
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from app.engine.constants import DT
from app.engine.engine import kickoff, step
from app.engine.executor import BehaviorExecutor
from app.engine.state import MatchState
from app.ws.connection_manager import ConnectionManager
from app.ws.match.coach import (
    CoachSetup,
    apply_coach_orders,
    coach_codes,
    coach_snapshots,
)
from app.ws.match.info import MatchInfo
from app.ws.match.messages import (
    goal_message,
    match_finished_message,
    match_resumed_message,
    match_started_message,
    match_state_message,
    pause_start_message,
    substitution_made_message,
)
from app.ws.match.pauses import (
    COOLING_BREAK_SECONDS,
    HALFTIME_SECONDS,
    Pause,
    pauses_schedule,
)
from app.ws.match.substitutions import PendingSubstitution, execute_substitution

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
    # clubes y alineaciones de matchStarted (al día con las sustituciones)
    info: MatchInfo
    match_start: datetime  # cuándo termina la espera y empieza a correr el partido
    # fase interna del runner
    phase: Phase = Phase.WAITING
    # último matchState ya serializado, para el que se conecta
    last_state: dict | None = None
    # inicio de la pausa en curso ya serializado para el que se une justo en la pausa
    current_pause: dict | None = None
    # team_id -> la sustitucion pedida por un club
    pending_substitutions: dict[str, PendingSubstitution] = field(default_factory=dict)
    # cuantas pausas empezaron
    pauses_started: int = 0
    # team_id -> DT del club. Se fija al arrancar: activar o quitar el DT
    # durante el partido no lo cambia. Un club que no está juega sin DT.
    coaches: dict[str, CoachSetup] = field(default_factory=dict)
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
    pauses: bool = True,
    coaches: dict[str, CoachSetup] | None = None,
) -> LiveMatch:
    """Prepara el partido, lo anota en live_matches y lo larga como tarea de fondo.
    codes = player_id -> código del comportamiento.
    coaches = team_id -> DT del club (los clubes sin DT no aparecen).
    Es sync pero usa create_task: hay que llamarla dentro del event loop."""
    if match_id in live_matches:
        return live_matches[match_id]  # ya se está jugando: no lo largamos dos veces

    coaches = coaches or {}
    kickoff(state)
    live = LiveMatch(
        match_id=match_id,
        state=state,
        executor=BehaviorExecutor(state, codes, coach_codes(coaches, info)),
        info=info,
        match_start=datetime.now(timezone.utc) + timedelta(seconds=start_delay),
        coaches=coaches,
    )
    # el que se conecta durante la espera ya ve a los jugadores en formación (tick 0)
    live.last_state = _state_payload(live)
    live_matches[match_id] = live
    live.task = asyncio.create_task(
        run_match(
            live, tick_interval, start_delay, cooling_break_duration, halftime_duration, pauses=pauses
        )
    )
    return live


def _execute_pending_subs(live: LiveMatch) -> list[PendingSubstitution]:
    """Ejecuta las sustituciones pendientes y devuelve las que se hicieron."""
    pending = live.pending_substitutions.copy()
    live.pending_substitutions.clear()
    executed = []
    for team_id, sub in pending.items():
        execute_substitution(live.state, live.info, live.executor, team_id, sub)
        executed.append(sub)
    return executed


async def _pause(live: LiveMatch, pause: Pause, seconds: float) -> None:
    """Avisa la pausa, espera y avisa la reanudación del partido"""
    match_id = str(live.match_id)
    live.current_pause = pause_start_message(
        match_id, live.state, pause, seconds
    ).model_dump(mode="json")
    live.phase = Phase.PAUSED
    live.pauses_started += 1
    await match_connections.broadcast(live.match_id, live.current_pause)

    await asyncio.sleep(seconds)

    if pause == Pause.HALFTIME:
        kickoff(live.state)
    live.phase = Phase.PLAYING
    live.current_pause = None

    executed_subs = _execute_pending_subs(live)
    if executed_subs:
        # el que se conecte justo después de los cambios tiene que ver los que entraron
        live.last_state = _state_payload(live)
    for sub in executed_subs:
        msg = substitution_made_message(match_id, live.state, sub)
        await match_connections.broadcast(
            live.match_id, msg.model_dump(mode="json", exclude_none=True)
        )

    resumed = match_resumed_message(match_id, live.state, pause)
    await match_connections.broadcast(live.match_id, resumed.model_dump(mode="json"))


async def _tick(live: LiveMatch, rng: random.Random) -> None:
    """Avanza el partido un tick:
    decide (jugadores y DT) -> step -> goal(s) -> matchState -> órdenes del DT."""
    actions, orders = await live.executor.decide_with_coach(
        live.state, coach_snapshots(live)
    )
    goals = step(live.state, actions, rng)

    for goal in goals:
        message = goal_message(str(live.match_id), goal, live.state)
        await match_connections.broadcast(
            live.match_id, message.model_dump(mode="json")
        )

    live.last_state = _state_payload(live)
    await match_connections.broadcast(live.match_id, live.last_state)

    # las órdenes se aplican después del step: los jugadores de este tick ya
    # decidieron, así que un cambio de comportamiento rige desde el tick siguiente
    for message in apply_coach_orders(live, orders):
        await match_connections.broadcast(live.match_id, message)


async def _notify_finish(live: LiveMatch) -> None:
    """Avisa que el partido terminó bien"""
    finished = match_finished_message(str(live.match_id), live.state)
    await match_connections.broadcast(live.match_id, finished.model_dump(mode="json"))


async def _clear(live: LiveMatch) -> None:
    """Cierra el partido, haya terminado bien o con error: lo saca de live_matches,
    cierra las conexiones y el executor."""
    live.phase = Phase.FINISHED
    live_matches.pop(live.match_id, None)
    await match_connections.close_all(live.match_id)
    live.executor.close()

async def stop_match(live: LiveMatch) -> None:
    """Corta un partido en curso y lo limpia, aunque la tarea no haya llegado a arrancar."""
    if live.task is not None:
        live.task.cancel()
        with contextlib.suppress(asyncio.CancelledError): # esperamos a que termine de cortarse (el CancelledError es lo esperado)
            await live.task
    await _clear(live) # si el finally de run_match nunca se corrio limpiamos aca

async def run_match(
    live: LiveMatch,
    tick_interval: float = DT,
    start_delay: float = START_DELAY_SECONDS,
    cooling_break_duration: float = COOLING_BREAK_SECONDS,
    halftime_duration: float = HALFTIME_SECONDS,
    pauses: bool = True
) -> None:
    """Espera start_delay, juega hasta total_ticks con las pausas en el medio
    y avisa el final. Pase lo que pase, al final cierra el partido con _clear."""
    loop = asyncio.get_running_loop()
    rng = random.Random()
    try:
        pause_schedule = pauses_schedule(live.state.total_ticks) if pauses else {}
        await asyncio.sleep(start_delay)
        live.phase = Phase.PLAYING
        next_tick = loop.time()
        while live.state.tick < live.state.total_ticks:
            await _tick(live, rng)

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

        await _notify_finish(live)
    except Exception:
        logger.exception("El partido %s se cortó por un error", live.match_id)
    finally:
        await _clear(live)


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
