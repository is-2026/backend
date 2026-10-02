import random
from math import copysign, hypot

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
from app.engine.state import MatchState, Side


def _scale(attr: int, value_range: tuple[float, float]) -> float:
    """Convierte un atributo PACSS (20-100) a su valor físico, en forma lineal."""
    low, high = value_range
    t = (attr - ATTR_MIN) / (ATTR_MAX - ATTR_MIN)
    return low + t * (high - low)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _reset_positions(
    state: MatchState,
) -> None:
    """Jugadores vuelven a la formación inicial y la pelota al centro."""
    state.ball.x, state.ball.y = 0.0, 0.0
    state.ball.vx, state.ball.vy = 0.0, 0.0
    state.ball.last_touch_id = None

    home_i = 0
    away_i = 0
    for player in state.players:
        if player.side == Side.HOME:
            player.x, player.y = state.home_formation[home_i]
            home_i += 1
        else:  # Side.AWAY
            x, y = state.away_formation[away_i]
            player.x, player.y = (-x, -y)
            away_i += 1
        player.cooldown = 0


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


def _ball_in_goal(state: MatchState) -> bool:
    """La pelota entró en el arco."""
    ball = state.ball
    return abs(ball.x) >= FIELD_HALF_LENGTH and abs(ball.y) <= GOAL_HALF_WIDTH


def _move_ball(state: MatchState) -> None:
    ball = state.ball
    # primero avanza en los dos ejes para saber si entró al arco
    ball.x += ball.vx * DT
    ball.y += ball.vy * DT

    # si entró al arco no rebota
    if _ball_in_goal(state):
        return

    # rebote: se pega al borde y la velocidad queda apuntando hacia adentro
    if abs(ball.x) >= FIELD_HALF_LENGTH:
        ball.x = copysign(FIELD_HALF_LENGTH, ball.x)
        ball.vx = copysign(ball.vx * BALL_BOUNCE, -ball.x)
    if abs(ball.y) >= FIELD_HALF_WIDTH:
        ball.y = copysign(FIELD_HALF_WIDTH, ball.y)
        ball.vy = copysign(ball.vy * BALL_BOUNCE, -ball.y)

    ball.vx *= BALL_FRICTION
    ball.vy *= BALL_FRICTION

    if hypot(ball.vx, ball.vy) < BALL_STOP_SPEED:
        ball.vx = 0.0
        ball.vy = 0.0


def _check_goal(state: MatchState) -> GoalEvent | None:
    """Si la pelota entró en un arco: suma el gol, arma el evento y reinicia."""
    if not _ball_in_goal(state):
        return None

    # el local ataca hacia +x. si entró en el arco de la derecha, es gol del local
    if state.ball.x > 0:
        state.home_score += 1
        team_id = state.home_team_id
    else:
        state.away_score += 1
        team_id = state.away_team_id

    event = GoalEvent(
        tick=state.tick,
        # el último que la tocó, aunque sea gol en contra
        player_id=state.ball.last_touch_id,
        team_id=team_id,
        minute=state.tick // TICKS_PER_MINUTE,
    )
    _reset_positions(state)
    return event


def _decrease_cooldowns(state: MatchState) -> None:
    for player in state.players:
        if player.cooldown > 0:
            player.cooldown -= 1


def step(
    state: MatchState,
    actions: dict[str, Action],
    rng: random.Random,
) -> list[GoalEvent]:
    """Avanza la simulación un tick. Modifica `state` y devuelve los eventos.
    `actions` va de player_id a la acción de ese jugador.
    si un jugador no está en el dict, no hizo nada en este tick.
    """
    events: list[GoalEvent] = []
    _move_players(state, actions)
    _move_ball(state)

    goal = _check_goal(state)
    if goal is not None:
        events.append(goal)

    _decrease_cooldowns(state)
    state.tick += 1

    return events
