import asyncio
import logging

from app.engine.actions import Action
from app.engine.behavior_exec import Snapshot, take_snapshot
from app.engine.constants import CLOSE_TIMEOUT, STARTUP_DEADLINE, TICK_DEADLINE
from app.engine.sandbox import start_worker
from app.engine.state import MatchState, PlayerState, Side

logger = logging.getLogger(__name__)


class _TeamWorker:
    """Un proceso hijo con los comportamientos de un equipo."""

    def __init__(self, side: Side, players: list[PlayerState], codes: dict[str, str]):
        self._side = side
        self._proc, self._conn = start_worker(players, codes)
        self._started = False  # ya contestó alguna vez?
        self._dead = False

    async def decide(
        self, snapshot: Snapshot, player_ids: list[str]
    ) -> dict[str, Action]:
        if self._dead:
            return {}
        deadline = TICK_DEADLINE if self._started else STARTUP_DEADLINE
        try:
            self._conn.send(("decide", snapshot, player_ids))
            ready = await asyncio.to_thread(self._conn.poll, deadline)
            if not ready:
                self._kill()
                logger.warning(
                    "El hijo de %s no contestó en %s s", self._side, deadline
                )
                return {}
            actions = self._conn.recv()
        except (EOFError, OSError):
            self._kill()
            logger.warning("El hijo de %s se murió", self._side)
            return {}
        self._started = True
        return actions

    def set_behavior(self, player: PlayerState, code: str) -> None:
        if self._dead:
            return
        try:
            self._conn.send(("set", player, code))
        except OSError:
            self._kill()

    def close(self) -> None:
        if self._dead:
            return  # no hago nada porque ya está muerto
        try:
            self._conn.send(("close",))
        except OSError:
            pass
        self._proc.join(CLOSE_TIMEOUT)
        self._kill()

    def _kill(self) -> None:
        if self._proc.is_alive():
            self._proc.kill()
        self._proc.join()
        self._conn.close()
        self._dead = True


class BehaviorExecutor:
    """Un hijo por equipo: si un comportamiento tramposo mata al suyo,
    solo se congela su equipo."""

    def __init__(self, state: MatchState, codes: dict[str, str]):
        self._state = state
        self._workers = {
            side: _TeamWorker(side, [p for p in state.players if p.side == side], codes)
            for side in Side
        }

    async def decide(self, state: MatchState) -> dict[str, Action]:
        calls = []
        for side, worker in self._workers.items():
            snapshot = take_snapshot(state, side)
            player_ids = [p.id for p in state.players if p.side == side]
            calls.append(worker.decide(snapshot, player_ids))
        actions = {}
        for team_actions in await asyncio.gather(*calls):  # los dos en paralelo
            actions.update(team_actions)
        return actions

    def set_behavior(self, player_id: str, code: str) -> None:
        player = next((p for p in self._state.players if p.id == player_id), None)
        if player is None:
            logger.warning("No existe el jugador %s", player_id)
            return
        self._workers[player.side].set_behavior(player, code)

    def close(self) -> None:
        for worker in self._workers.values():
            worker.close()
