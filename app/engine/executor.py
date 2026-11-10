import asyncio
import logging

from app.engine.actions import Action
from app.engine.behavior_exec import CoachSnapshot, Snapshot, take_snapshot
from app.engine.coach_orders import CoachOrder
from app.engine.constants import CLOSE_TIMEOUT, STARTUP_DEADLINE, TICK_DEADLINE
from app.engine.sandbox import start_worker
from app.engine.state import MatchState, PlayerState, Side

logger = logging.getLogger(__name__)


class _TeamWorker:
    """Un proceso hijo con los comportamientos de un equipo."""

    def __init__(
        self,
        side: Side,
        players: list[PlayerState],
        codes: dict[str, str],
        coach_code: str | None = None,
    ):
        self._side = side
        self._proc, self._conn = start_worker(players, codes, coach_code)
        self._started = False  # ya contestó alguna vez?
        self._dead = False

    async def _request(self, message: tuple) -> object | None:
        # si no contesta a tiempo o se murio lo mato y devuelvo None
        if self._dead:
            return None
        deadline = TICK_DEADLINE if self._started else STARTUP_DEADLINE
        try:
            self._conn.send(message)
            ready = await asyncio.to_thread(self._conn.poll, deadline)
            if not ready:
                self._kill()
                logger.warning(
                    "El hijo de %s no contestó en %s s", self._side, deadline
                )
                return None
            response = self._conn.recv()
        except (EOFError, OSError):
            self._kill()
            logger.warning("El hijo de %s se murió", self._side)
            return None
        self._started = True
        return response

    async def decide(
        self,
        snapshot: Snapshot,
        player_ids: list[str],
        coach_snapshot: CoachSnapshot | None = None,
    ) -> tuple[dict[str, Action], list[CoachOrder]]:
        response = await self._request(("decide", snapshot, player_ids, coach_snapshot))
        if response is None:
            return {}, []
        return response

    async def decide_coach(self, coach_snapshot: CoachSnapshot) -> list[CoachOrder]:
        # para la llamada de penales
        response = await self._request(("coach", coach_snapshot))
        if response is None:
            return []
        return response

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

    def __init__(
        self,
        state: MatchState,
        codes: dict[str, str],
        coach_codes: dict[Side, str] | None = None,
    ):
        self._state = state
        coach_codes = coach_codes or {}
        self._workers = {
            side: _TeamWorker(
                side,
                [p for p in state.players if p.side == side],
                codes,
                coach_codes.get(side),
            )
            for side in Side
        }

    async def decide_with_coach(
        self, state: MatchState, coach_snapshots: dict[Side, CoachSnapshot]
    ) -> tuple[dict[str, Action], dict[Side, list[CoachOrder]]]:
        """Devuelve las acciones y las ordenes de cada DT por lado"""
        sides = list(self._workers)
        calls = []
        for side in sides:
            snapshot = take_snapshot(state, side)
            player_ids = [p.id for p in state.players if p.side == side]
            calls.append(
                self._workers[side].decide(
                    snapshot, player_ids, coach_snapshots.get(side)
                )
            )
        actions = {}
        orders = {}
        # los dos en paralelo
        results = await asyncio.gather(*calls)
        for side, (team_actions, team_orders) in zip(sides, results, strict=True):
            actions.update(team_actions)
            orders[side] = team_orders
        return actions, orders

    async def decide(self, state: MatchState) -> dict[str, Action]:
        actions, _ = await self.decide_with_coach(state, {})
        return actions

    async def decide_coaches(
        self, coach_snapshots: dict[Side, CoachSnapshot]
    ) -> dict[Side, list[CoachOrder]]:
        sides = list(coach_snapshots)
        calls = [
            self._workers[side].decide_coach(coach_snapshots[side]) for side in sides
        ]
        results = await asyncio.gather(*calls)
        return dict(zip(sides, results, strict=True))

    def set_behavior(self, player_id: str, code: str) -> None:
        player = next((p for p in self._state.players if p.id == player_id), None)
        if player is None:
            logger.warning("No existe el jugador %s", player_id)
            return
        self.set_player_behavior(player, code)

    def set_player_behavior(self, player: PlayerState, code: str) -> None:
        """Como set_behavior, pero sirve para un jugador que no está en cancha
        (por ejemplo, un suplente que patea en la tanda de penales)."""
        self._workers[player.side].set_behavior(player, code)

    def close(self) -> None:
        for worker in self._workers.values():
            worker.close()
