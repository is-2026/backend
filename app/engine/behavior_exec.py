import logging
from collections.abc import Callable
from dataclasses import dataclass
from math import hypot, isfinite
from types import CodeType

from app.engine.actions import Action, Move, PassTo, Shoot, ShootAtGoal
from app.engine.engine import control_radius
from app.engine.state import MatchState, PlayerState, Side
from app.engine.validation import InvalidBehaviorCode

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


def _to_view(x: float, y: float, side: Side) -> tuple[float, float]:
    # el estado tiene las posiciones en absoluto
    # los comportamientos piensan que estan como home
    # si es away lo doy vuelta para que piense que es home
    return (x, y) if side == Side.HOME else (-x, -y)


def _to_number(value: object) -> float:
    """Convierte un argumento de una primitiva a float.
    Rechaza nan e inf, el motor no los maneja"""
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"se esperaba un número finito, llegó {value!r}")
    return number


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
    # el filename es lo que aparece en el traceback por ej: File "<behavior h1>", line x
    # la sintaxis se valida al guardar el comportamiento, acá es solo defensa
    try:
        return compile(code, f"<behavior {name}>", "exec")
    except SyntaxError as e:
        raise InvalidBehaviorCode(str(e)) from e


class PlayerBrain:
    def __init__(self, player: PlayerState, code: CodeType):
        self._player_id = player.id
        self._side = player.side
        self._control_radius = control_radius(player.control)

        self._decide: Callable[[], None] | None

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
            "pass_to": self.pass_to,
            "shoot": self.shoot,
            "shoot_arco": self.shoot_arco,
        }
        try:
            exec(code, namespace)
        except Exception:
            logger.exception(
                "No se pudo cargar el comportamiento del jugador %s",
                self._player_id,
            )
            self._decide = None
        else:
            self._decide = namespace.get("decide_action")
            if self._decide is None:
                logger.warning(
                    "El comportamiento del jugador %s no define decide_action()",
                    self._player_id,
                )

    # --- primitivas de lectura ---
    def my_pos(self) -> tuple[float, float]:
        me = next(p for p in self._snapshot.teammates if p.id == self._player_id)
        return me.x, me.y

    def ball_pos(self) -> tuple[float, float]:
        return self._snapshot.ball.x, self._snapshot.ball.y

    def has_ball(self) -> bool:
        player_x, player_y = self.my_pos()
        ball_x, ball_y = self.ball_pos()
        distance = hypot(ball_x - player_x, ball_y - player_y)
        return distance <= self._control_radius

    def team_pos(self) -> list[tuple[str, float, float]]:
        return [
            (p.id, p.x, p.y)
            for p in self._snapshot.teammates
            if p.id != self._player_id
        ]

    def enemy_pos(self) -> list[tuple[str, float, float]]:
        return [(p.id, p.x, p.y) for p in self._snapshot.rivals]

    def score(self) -> tuple[int, int]:
        return self._snapshot.own_score, self._snapshot.rival_score

    def time(self) -> int:
        return self._snapshot.tick

    def total_time(self) -> int:
        return self._snapshot.total_ticks

    # --- primitivas de acción ---
    def move(self, dx: float, dy: float, speed_pct: float):
        if self._action is None:
            dx, dy = _to_view(_to_number(dx), _to_number(dy), self._side)
            self._action = Move(dx, dy, _to_number(speed_pct))

    def pass_to(self, player_id: str):
        if self._action is None:
            self._action = PassTo(str(player_id))

    def shoot(self, dx: float, dy: float, power_pct: float):
        if self._action is None:
            dx, dy = _to_view(_to_number(dx), _to_number(dy), self._side)
            self._action = Shoot(dx, dy, _to_number(power_pct))

    def shoot_arco(self):
        if self._action is None:
            self._action = ShootAtGoal()

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


def create_brains(state: MatchState, codes: dict[str, str]) -> dict[str, PlayerBrain]:
    """Arma los brains al iniciar el partido: compila el código una sola vez.
    codes = player.id -> código del jugador
    Si un jugador no tiene código o no compila, no se le arma brain"""
    brains: dict[str, PlayerBrain] = {}
    for player in state.players:
        code = codes.get(player.id)
        if code is None:
            continue
        try:
            compiled_code = compile_behavior(code, player.id)
        except InvalidBehaviorCode:
            logger.exception("El comportamiento del jugador %s no compila", player.id)
            continue
        brains[player.id] = PlayerBrain(player, compiled_code)
    return brains


def decide_actions(
    state: MatchState, brains: dict[str, PlayerBrain]
) -> dict[str, Action]:
    """Corre decide_action de cada jugador y devuelve las acciones para step().
    Se llama antes de step(), así todos leen el mismo estado."""
    snapshots = {side: take_snapshot(state, side) for side in Side}

    actions: dict[str, Action] = {}
    for player in state.players:
        brain = brains.get(player.id)
        if brain is None:
            continue
        action = brain.run(snapshots[player.side])
        if action is not None:
            actions[player.id] = action
    return actions
