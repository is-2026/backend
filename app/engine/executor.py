import asyncio
import logging

from app.engine.actions import Action
from app.engine.behavior_exec import take_snapshot
from app.engine.constants import CLOSE_TIMEOUT, STARTUP_DEADLINE, TICK_DEADLINE
from app.engine.sandbox import start_worker
from app.engine.state import MatchState, Side

logger = logging.getLogger(__name__)


class BehaviorExecutor:
    def __init__(self, state: MatchState, codes: dict[str, str]):
        self._state = state
        self._proc, self._conn = start_worker(state.players, codes)
        self._started = False  # ya contestó alguna vez?
        self._dead = False

    async def decide(self, state: MatchState) -> dict[str, Action]:
        if self._dead:
            return {}
        snapshots = {side: take_snapshot(state, side) for side in Side}
        players_on_field = [(p.id, p.side) for p in state.players]
        deadline = TICK_DEADLINE if self._started else STARTUP_DEADLINE
        try:
            self._conn.send(("decide", snapshots, players_on_field))
            ready = await asyncio.to_thread(self._conn.poll, deadline)
            if not ready:
                self._kill()
                logger.warning("No constestó en %s s", deadline)
                return {}
            actions = self._conn.recv()
        except (EOFError, OSError):
            self._kill()
            logger.warning("No constestó en %s s", deadline)
            return {}
        self._started = True
        return actions

    def set_behavior(self, player_id: str, code: str) -> None:
        player = next(
            (player for player in self._state.players if player.id == player_id), None
        )
        if player is None:
            logger.warning("No existe el jugador %s", player_id)
            return
        if self._dead:
            return
        try:
            self._conn.send(("set", player, code))
        except OSError:
            self._kill()

    def close(self):
        if self._dead:
            return  # no hago nada porque ya está muerto
        try:
            self._conn.send(("close",))
        except OSError:
            pass
        self._proc.join(CLOSE_TIMEOUT)
        self._kill()

    def _kill(self):
        if self._proc.is_alive():
            self._proc.kill()
        self._proc.join()
        self._conn.close()
        self._dead = True
