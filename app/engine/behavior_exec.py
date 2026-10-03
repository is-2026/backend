import logging
from collections.abc import Callable
from dataclasses import dataclass
from types import CodeType

from app.engine.actions import Action, Move, PassTo, Shoot, ShootAtGoal
from app.engine.state import MatchState, PlayerState, Side

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayerSnapshot:
    id: str
    x: float
    y: float


@dataclass(frozen=True)
class BallSnapshot:
    x: float
    y: float


@dataclass(frozen=True)
class Snapshot:
    teammates: tuple[PlayerSnapshot, ...]  # incluye al propio jugador
    rivals: tuple[PlayerSnapshot, ...]
    ball: BallSnapshot
    own_score: int
    rival_score: int
    tick: int
    total_ticks: int


class InvalidBehaviorCode(Exception):
    """Comportamiento con sintaxis inválida"""


def _to_view(x: float, y: float, side: Side.Home) -> tuple[float, float]:
    # el estado tiene las posiciones en absoluto
    # los comportamientos piensan que estan como home
    # si es away lo doy vuelta para que piense que es home
    return (x, y) if side == Side.HOME else (-x, -y)


def take_snapshot(state: MatchState, side: Side) -> Snapshot:
    """Arma la foto que ve cada lado. Si es away espeja las coordenadas, las vuelve home"""

    teammates: list[PlayerSnapshot] = []
    rivals: list[PlayerSnapshot] = []
    for player in state.players:
        x, y = _to_view(player.x, player.y, side)
        if player.side == side:
            teammates.append(PlayerSnapshot(player.id, x, y))
        else:
            rivals.append(PlayerSnapshot(player.id, x, y))

    ball_x, ball_y = _to_view(state.ball.x, state.ball.y, side)

    if side == Side.HOME:
        own_score, rival_score = state.home_score, state.away_score
    else:
        own_score, rival_score = state.away_score, state.home_score

    return Snapshot(
        teammates=tuple(teammates),
        rivals=tuple(rivals),
        ball=BallSnapshot(ball_x, ball_y),
        own_score=own_score,
        rival_score=rival_score,
        tick=state.tick,
        total_ticks=state.total_ticks,
    )


def compile_behavior(code: str, name: str) -> CodeType:
    # el filename es lo que aparece en el traceback por ej: File "<behavior Atacante>", line x
    # para pensar en un futuro: cuándo se verifica la sintaxis del código?
    # a este momento llega el código full verificado o no?
    try:
        return compile(code, f"<behavior {name}>", "exec")
    except SyntaxError as e:
        raise InvalidBehaviorCode(str(e)) from e


class PlayerBrain:
    def __init__(self, player: PlayerState, code: CodeType):
        self._player_id = player.id
        self._side = player.side
        self._control = player.control

        self._action: Action | None = None
        self._snapshot: Snapshot | None = None

        namespace = {
            "my_pos": self.my_pos,
            "ball_pos": self.ball_pos,
            "has_ball": self.has_ball,
            "team_pos": self.team_pos,
            "enemy_pos": self.enemy_pos,
            "score": self.score,
            "time": self.time,
            "total_time": self.total_time,
            "move": self.move,
        }
        try:
            exec(code, namespace)
        except Exception:
            logger.exception("Código con excepciones, no hago nada")
            self._decide = None
        else:
            self._decide: Callable[[], None] | None = namespace.get("decide_action")

    # --- primitivas de lectura ---
    def my_pos(self) -> tuple[float, float]:
        me = next(p for p in self._snapshot.teammates if p.id == self._player_id)
        return me.x, me.y

    def ball_pos(self) -> tuple[float, float]:
        return self._snapshot.ball.x, self._snapshot.ball.y

    def has_ball(self) -> bool:
        pass

    def team_pos(self) -> list[tuple[str, float, float]]:
        pass

    def enemy_pos(self) -> list[tuple[str, float, float]]:
        pass

    def score(self) -> tuple[int, int]:
        pass

    def time(self) -> int:
        pass

    def total_time(self) -> int:
        pass

    # --- primitivas de acción ---
    def move(self, dx: float, dy: float, speed_pct: float):
        if self._action is None:
            self._action = Move(float(dx), float(dy), float(speed_pct))

    def pass_to(self, player_id: str):
        pass

    def shoot(self, dx: float, dy: float, power_pct: float):
        pass

    def shoot_arco(self):
        pass

    def run(self, snapshot: Snapshot) -> Action | None:
        self._snapshot = snapshot
        self._action = None
        if self._decide is None:
            return None
        try:
            self._decide()
        except Exception:
            logger.exception(
                "El comportamiento del jugador %s falló en decide_action()",
                self._player_id,
            )
            return None
        return self._action
