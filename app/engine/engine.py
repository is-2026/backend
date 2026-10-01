import random
from math import hypot

from app.engine.actions import Action, Move, PassTo, Shoot, ShootAtGoal
from app.engine.constants import ATTR_MAX, ATTR_MIN, DT, SPEED_MAX_RANGE
from app.engine.events import GoalEvent
from app.engine.state import MatchState


def _scale(attr: int, value_range: tuple[float, float]) -> float:
    """Convierte un atributo PACSS (20-100) a su valor físico, en forma lineal."""
    low, high = value_range
    t = (attr - ATTR_MIN) / (ATTR_MAX - ATTR_MIN)
    return low + t * (high - low)


def _reset_positions(state: MatchState) -> None:
    """Jugadores vuelven a la formación inicial y la pelota al centro."""
    pass


def _normalize_vector(dx: float, dy: float) -> tuple[float, float]:
    magnitude = hypot(dx, dy)

    if magnitude == 0:
        return 0.0, 0.0

    return dx / magnitude, dy / magnitude


def step(
    state: MatchState,
    actions: dict[str, Action],
    rng: random.Random,
) -> list[GoalEvent]:
    """Avanza la simulación un tick. Modifica `state` y devuelve los eventos.

    `actions` va de player_id a la acción de ese jugador; si un jugador no
    está en el dict, no hizo nada en este tick.
    """
    events: list[GoalEvent] = []
    # 1. mover jugadores
    # 2. mover la pelota: fricción, rebote y gol
    # 3. bajar cooldowns y avanzar el tick
    # 4. resolver golpear a la pelota? pensar
    for player in state.players:
        action = actions.get(player.id)
        if isinstance(action, Move):
            x_normalized, y_normalized = _normalize_vector(action.dx, action.dy)
            max_speed = _scale(player.speed, SPEED_MAX_RANGE)
            pct = action.speed_pct / 100
            player.x += x_normalized * pct * max_speed * DT
            player.y += y_normalized * pct * max_speed * DT
    state.tick += 1

    return events
