import random
from math import hypot, copysign

from app.engine.actions import Action, Move, PassTo, Shoot, ShootAtGoal
from app.engine.constants import (
    ATTR_MAX,
    ATTR_MIN,
    BALL_BOUNCE,
    BALL_FRICTION,
    BALL_STOP_SPEED,
    CONTROL_RADIUS_RANGE,
    COOLDOWN_TICKS_RANGE,
    DT,
    FIELD_HALF_LENGTH,
    FIELD_HALF_WIDTH,
    GOAL_HALF_WIDTH,
    KICK_SPEED_RANGE,
    SPEED_MAX_RANGE,
    TICKS_PER_MINUTE,
    TICKS_PER_SECOND,
    TRIANGLE_HOME,
)
from app.engine.events import GoalEvent
from app.engine.state import MatchState


def _scale(attr: int, value_range: tuple[float, float]) -> float:
    """Convierte un atributo PACSS (20-100) a su valor físico, en forma lineal."""
    low, high = value_range
    t = (attr - ATTR_MIN) / (ATTR_MAX - ATTR_MIN)
    return low + t * (high - low)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _reset_positions(state: MatchState) -> None:
    """Jugadores vuelven a la formación inicial y la pelota al centro."""
    pass


def _normalize_vector(dx: float, dy: float) -> tuple[float, float]:
    magnitude = hypot(dx, dy)

    if magnitude == 0:
        return 0.0, 0.0

    return dx / magnitude, dy / magnitude


def _move_players(state: MatchState, actions: dict[str, Action]) -> None:
    for player in state.players:
        action = actions.get(player.id)
        if isinstance(action, Move):
            x_normalized, y_normalized = _normalize_vector(action.dx, action.dy)
            max_speed = _scale(player.speed, SPEED_MAX_RANGE)
            pct = _clamp(action.speed_pct, 0, 100) / 100
            player.x += x_normalized * pct * max_speed * DT
            player.x = _clamp(player.x, -FIELD_HALF_LENGTH, FIELD_HALF_LENGTH)
            player.y += y_normalized * pct * max_speed * DT
            player.y = _clamp(player.y, -FIELD_HALF_WIDTH, FIELD_HALF_WIDTH)


def _move_ball(state: MatchState) -> None:
    ball = state.ball
    # movemos la pelota en la velocidad guardada
    ball.x += ball.vx * DT
    # si toca con el borde derecho/izquierdo
    if abs(ball.x) >= FIELD_HALF_LENGTH:
        # le pongo la pos x del borde donde choco
        ball.x = copysign(FIELD_HALF_LENGTH, ball.x)
        # invierto el componente de velocidad en x
        ball.vx = copysign(ball.vx * BALL_BOUNCE, -ball.x)

    ball.y += ball.vy * DT
    # si choca con el borde de arriba/abajo
    if abs(ball.y) >= FIELD_HALF_WIDTH:
        ball.y = copysign(FIELD_HALF_WIDTH, ball.y)
        ball.vy = copysign(ball.vy * BALL_BOUNCE, -ball.y)

    ball.vx *= BALL_FRICTION
    ball.vy *= BALL_FRICTION

    if hypot(ball.vx, ball.vy) < BALL_STOP_SPEED:
        ball.vx = 0.0
        ball.vy = 0.0


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
    _move_players(state, actions)
    # 2. mover la pelota: fricción, rebote y gol
    _move_ball(state)
    # 3. bajar cooldowns y avanzar el tick
    # 4. resolver golpear a la pelota? pensar

    state.tick += 1

    return events
