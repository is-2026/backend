import builtins
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from math import hypot, isfinite
from types import CodeType, SimpleNamespace

from app.engine.actions import Action, Move, PassTo, Shoot, ShootAtGoal
from app.engine.coach_orders import CoachOrder, PenaltyOrder, SetBehavior, Substitute
from app.engine.constants import PENALTIES_PER_TEAM
from app.engine.engine import control_radius
from app.engine.state import MatchState, PlayerState, Side
from app.engine.validation import InvalidBehaviorCode

logger = logging.getLogger(__name__)


# Lo único de python que puede usar un comportamiento (además de import math)
# Lo que no está acá (open, eval, ...) no existe al ejecutar
SAFE_BUILTINS = (
    "abs",
    "min",
    "max",
    "round",
    "sum",
    "len",
    "range",
    "enumerate",
    "zip",
    "sorted",
    "reversed",
    "map",
    "filter",
    "any",
    "all",
    "isinstance",
    "list",
    "dict",
    "tuple",
    "set",
    "float",
    "int",
    "bool",
    "str",
    "Exception",
    "ValueError",
    "TypeError",
    "ZeroDivisionError",
    "IndexError",
    "KeyError",
)


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


@dataclass(frozen=True)
class CoachSnapshot:
    own_score: int
    rival_score: int
    tick: int
    total_ticks: int
    on_field: tuple[tuple[str, str], ...]  # (player_id, behavior_id)
    bench: tuple[str, ...]  # player_id
    behaviors: tuple[tuple[str, str], ...]  # (behavior_id, nombre) de jugador
    penalty_shootout: bool  # True solo en la llamada de la ventana de penales


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


def _safe_builtins() -> dict[str, object]:
    """Builtins de un brain. Cada brain recibe un dict y un math propios:
    si un comportamiento hace math.pi = 3 o pisa abs, no le cambia nada a otro"""
    public = {name: getattr(math, name) for name in dir(math) if name[0] != "_"}
    own_math = SimpleNamespace(**public)

    def import_only_math(name, globals=None, locals=None, fromlist=(), level=0):
        # Python lo llama en cada import
        return own_math

    safe = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    safe["__import__"] = import_only_math
    return safe


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
            "__builtins__": _safe_builtins(),
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
        except MemoryError:
            raise  # para que no me lo coma el except Exception
        except Exception:
            logger.exception(
                "El comportamiento del jugador %s falló en decide_action()",
                self._player_id,
            )
            return None
        return self._action


def load_brain(player: PlayerState, code: str) -> PlayerBrain | None:
    try:
        compiled_code = compile_behavior(code, player.id)
    except InvalidBehaviorCode:
        logger.exception("El comportamiento del jugador %s no compila", player.id)
        return None
    return PlayerBrain(player, compiled_code)


def _check_input_penalty(value: object) -> bool:
    return (
        isinstance(value, (list, tuple)) and len(value) == 2
    )  # chequea que cada pateador que pasa DT al penalty sea una lista o una tupla de 2 elementos


class CoachBrain:
    """El DT de un equipo. Solo se aplican las reglas que dependen
    del propio DT (cuándo vale cada primitiva y que gana la primera llamada)."""

    def __init__(self, side: Side, code: CodeType):
        self._side = side

        self._decide: (
            Callable[[], None] | None
        )  # Callable es para decir, che self._decide puede ser llamado como una funcion.

        self._snapshot: CoachSnapshot | None = None
        self._orders: list[CoachOrder] = []  # cargo lo que pide el DT
        # para que gane la primera llamada en cada run
        self._players_ordered: set[str] = (
            set()
        )  # Para ignorar en caso que el DT vuelva a asignarle un set_behavior al mismo player
        self._substituted = False  # para indicar si ya hizo una sustitucion o no
        self._penalty_ordered = False  # para indicar si el dt llamo a penalty_order

        namespace = {
            "__builtins__": _safe_builtins(),  # funciones de python que puede usar el codigo
            "score": self.score,  ##Primitivas.
            "time": self.time,
            "total_time": self.total_time,
            "on_field": self.on_field,
            "bench": self.bench,
            "behaviors": self.behaviors,
            "is_penalty_shootout": self.is_penalty_shootout,
            "set_behavior": self.set_behavior,
            "substitute": self.substitute,
            "penalty_order": self.penalty_order,
        }
        try:
            exec(code, namespace)
        except Exception:
            logger.exception("No se pudo cargar el DT de %s", self._side)
            self._decide = None
        else:
            self._decide = namespace.get("decide_coach")
            if self._decide is None:
                logger.warning("El DT de %s no define decide_coach()", self._side)

    # --- primitivas de lectura ---
    def score(self) -> tuple[int, int]:
        return self._snapshot.own_score, self._snapshot.rival_score

    def time(self) -> int:
        return self._snapshot.tick

    def total_time(self) -> int:
        return self._snapshot.total_ticks

    def on_field(self) -> list[tuple[str, str]]:
        return list(self._snapshot.on_field)

    def bench(self) -> list[str]:
        return list(self._snapshot.bench)

    def behaviors(self) -> list[tuple[str, str]]:
        return list(self._snapshot.behaviors)

    def is_penalty_shootout(self) -> bool:
        return self._snapshot.penalty_shootout

    # --- primitivas de acción ---
    def set_behavior(self, player_id: str, behavior_id: str):
        if self._snapshot.penalty_shootout:
            return
        player_id, behavior_id = str(player_id), str(behavior_id)
        if player_id in self._players_ordered:
            return  # gana la primera para cada jugador
        self._players_ordered.add(player_id)
        # si ya tiene ese comportamiento no hago nada: así el hijo no lo recarga
        if (player_id, behavior_id) in self._snapshot.on_field:
            return
        self._orders.append(SetBehavior(player_id, behavior_id))

    def substitute(self, player_out_id: str, player_in_id: str, behavior_id: str):
        if self._snapshot.penalty_shootout or self._substituted:
            return  # el club puede tener una sola pendiente: gana la primera
        self._substituted = True
        self._orders.append(
            Substitute(str(player_out_id), str(player_in_id), str(behavior_id))
        )

    def penalty_order(self, kickers: list[tuple[str, str]]):
        if not self._snapshot.penalty_shootout or self._penalty_ordered:
            return
        # la primera llamada cuenta aunque esté mal formada
        self._penalty_ordered = True
        # si la forma es inválida se ignora sin lanzar: una excepción acá haría
        # perder todas las órdenes del DT en esta llamada
        if not isinstance(kickers, (list, tuple)) or len(kickers) != PENALTIES_PER_TEAM:
            return
        if not all(_check_input_penalty(kicker) for kicker in kickers):
            return
        pairs = tuple((str(player), str(behavior)) for player, behavior in kickers)
        self._orders.append(PenaltyOrder(pairs))

    def run(
        self, snapshot: CoachSnapshot
    ) -> list[CoachOrder]:  ## SE Ejecuta 1 vez por tick para ver que quiere hacer el DT
        self._snapshot = snapshot
        self._orders = []
        self._players_ordered = set()
        self._substituted = False
        self._penalty_ordered = False
        if self._decide is None:
            return []
        try:
            self._decide()
        except MemoryError:
            raise  # para que no me lo coma el except Exception
        except Exception:
            logger.exception("El DT de %s falló en decide_coach()", self._side)
            return []  # las órdenes anotadas antes del error no se aplican
        return self._orders


def load_coach_brain(
    side: Side, code: str
) -> CoachBrain | None:  ##para cargar un nuevo dt.
    try:
        compiled_code = compile_behavior(code, f"coach {side}")
    except InvalidBehaviorCode:
        logger.exception("El DT de %s no compila", side)
        return None
    return CoachBrain(side, compiled_code)


def create_brains(state: MatchState, codes: dict[str, str]) -> dict[str, PlayerBrain]:
    """Arma los brains al iniciar el partido: compila el código una sola vez.
    codes = player.id -> código del jugador
    Si un jugador no tiene código o no compila, no se le arma brain"""
    brains: dict[str, PlayerBrain] = {}
    for player in state.players:
        code = codes.get(player.id)
        if code is None:
            continue
        brain = load_brain(player, code)
        # si no compila que quede con el brain viejo
        if brain is not None:
            brains[player.id] = brain
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
