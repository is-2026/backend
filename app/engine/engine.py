import random
from math import copysign, cos, hypot, radians, sin

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
    SEPARATION_PASSES,
    SHOT_SPREAD_RANGE,
    SOCIAL_DISTANCING,
    SPEED_MAX_RANGE,
    TICKS_PER_MINUTE,
)
from app.engine.events import GoalEvent
from app.engine.state import BallState, MatchState, PlayerState, Side


def _scale(attr: int, value_range: tuple[float, float]) -> float:
    """Convierte un atributo PACSS (20-100) a su valor físico, en forma lineal."""
    low, high = value_range
    t = (attr - ATTR_MIN) / (ATTR_MAX - ATTR_MIN)
    return low + t * (high - low)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def kickoff(
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


def _avoid_players(
    player_id: str,
    step_x: float,
    step_y: float,
    initial_positions: dict[str, tuple[float, float]],
) -> tuple[float, float]:
    player_x, player_y = initial_positions[player_id]
    for other_id, (other_x, other_y) in initial_positions.items():
        if other_id == player_id:
            continue

        distance = hypot(player_x - other_x, player_y - other_y)
        if distance == 0.0:
            continue  # para que no explote por dividir por 0

        n_x, n_y = _normalize_vector(other_x - player_x, other_y - player_y)
        towards = step_x * n_x + step_y * n_y  # cuanto del paso va hacia otro jugador
        allowed = max(0.0, distance - SOCIAL_DISTANCING)
        if towards > allowed:
            step_x -= (towards - allowed) * n_x
            step_y -= (towards - allowed) * n_y

    return step_x, step_y


def _move_players(state: MatchState, actions: dict[str, Action]) -> None:
    # guardo las posiciones iniciales de los jugadores ya que lo voy a necesitar
    # para calcular la separación de los jugadores
    # (los jugadores se mueven todos al mismo tiempo)
    initial_positions = {player.id: (player.x, player.y) for player in state.players}
    for player in state.players:
        action = actions.get(player.id)
        if isinstance(action, Move):
            x_normalized, y_normalized = _normalize_vector(action.dx, action.dy)
            max_speed = _scale(player.speed, SPEED_MAX_RANGE)
            pct = _clamp(action.speed_pct, 0, 100) / 100
            step_x = x_normalized * pct * max_speed * DT
            step_y = y_normalized * pct * max_speed * DT
            step_x, step_y = _avoid_players(
                player.id, step_x, step_y, initial_positions
            )
            player.x = _clamp(player.x + step_x, -FIELD_HALF_LENGTH, FIELD_HALF_LENGTH)
            player.y = _clamp(player.y + step_y, -FIELD_HALF_WIDTH, FIELD_HALF_WIDTH)


def _separate_players(state: MatchState) -> None:
    for _ in range(SEPARATION_PASSES):
        for i in range(len(state.players)):
            for j in range(i + 1, len(state.players)):
                a, b = state.players[i], state.players[j]

                dx, dy = b.x - a.x, b.y - a.y
                distance = hypot(dx, dy)
                if distance >= SOCIAL_DISTANCING:
                    continue
                if distance == 0:
                    # misma posición exacta, rivales se separan en x, compañeros en y
                    nx, ny = (1.0, 0.0) if a.side != b.side else (0.0, 1.0)
                else:
                    nx, ny = dx / distance, dy / distance
                push = (SOCIAL_DISTANCING - distance) / 2
                a.x = _clamp(a.x - nx * push, -FIELD_HALF_LENGTH, FIELD_HALF_LENGTH)
                a.y = _clamp(a.y - ny * push, -FIELD_HALF_WIDTH, FIELD_HALF_WIDTH)
                b.x = _clamp(b.x + nx * push, -FIELD_HALF_LENGTH, FIELD_HALF_LENGTH)
                b.y = _clamp(b.y + ny * push, -FIELD_HALF_WIDTH, FIELD_HALF_WIDTH)


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
    kickoff(state)
    return event


def _decrease_cooldowns(state: MatchState) -> None:
    for player in state.players:
        if player.cooldown > 0:
            player.cooldown -= 1


KICK_ACTIONS = (Shoot, ShootAtGoal, PassTo)


def control_radius(control: int) -> float:
    """Calcula el radio de control, donde puede patear la pelota"""
    return _scale(control, CONTROL_RADIUS_RANGE)


def _can_kick(player: PlayerState, action: Action | None, ball: BallState) -> bool:
    if not isinstance(action, KICK_ACTIONS):
        return False
    if player.cooldown > 0:
        return False
    distance = hypot(ball.x - player.x, ball.y - player.y)
    return distance <= control_radius(player.control)


def _rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    return x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)


def _shot_error(rng: random.Random, control: int) -> float:
    """Ángulo aleatorio (en radianes) que se desvía un remate: más control, menos desvío."""
    spread = _scale(control, SHOT_SPREAD_RANGE)
    return radians(rng.uniform(-spread, spread))


def _resolve_kicks(
    state: MatchState, actions: dict[str, Action], rng: random.Random
) -> None:
    candidates: list[PlayerState] = [
        p for p in state.players if _can_kick(p, actions.get(p.id), state.ball)
    ]
    if not candidates:
        return

    max_strength = max(p.strength for p in candidates)
    strongest = [p for p in candidates if p.strength == max_strength]
    winner = rng.choice(strongest)

    action = actions[winner.id]
    ball = state.ball
    if isinstance(action, Shoot):
        x_normalized, y_normalized = _normalize_vector(action.dx, action.dy)
        speed_power = _scale(winner.power, KICK_SPEED_RANGE)
        pct = _clamp(action.power_pct, 0, 100) / 100
        vx = x_normalized * speed_power * pct
        vy = y_normalized * speed_power * pct
        vx, vy = _rotate(vx, vy, _shot_error(rng, winner.control))

    elif isinstance(action, ShootAtGoal):
        goal_x = FIELD_HALF_LENGTH if winner.side == Side.HOME else -FIELD_HALF_LENGTH
        dx = goal_x - ball.x
        dy = rng.uniform(-GOAL_HALF_WIDTH, GOAL_HALF_WIDTH) - ball.y
        x_normalized, y_normalized = _normalize_vector(dx, dy)
        speed_power = _scale(winner.power, KICK_SPEED_RANGE)
        vx = x_normalized * speed_power
        vy = y_normalized * speed_power
        vx, vy = _rotate(vx, vy, _shot_error(rng, winner.control))

    elif isinstance(action, PassTo):
        teammate = next((p for p in state.players if p.id == action.target_id), None)
        if teammate is None or teammate.side != winner.side or teammate.id == winner.id:
            return

        dx = teammate.x - ball.x
        dy = teammate.y - ball.y
        distance = hypot(dx, dy)
        x_normalized, y_normalized = _normalize_vector(dx, dy)
        speed = min(
            distance * (1 - BALL_FRICTION) / DT,
            _scale(winner.power, KICK_SPEED_RANGE),
        )
        vx = x_normalized * speed
        vy = y_normalized * speed

    ball.vx, ball.vy = vx, vy
    ball.last_touch_id = winner.id
    winner.cooldown = round(_scale(winner.agility, COOLDOWN_TICKS_RANGE))


def change_player(
    state: MatchState, player_out_id: str, player_in: PlayerState
) -> None:
    """Se hace el cambio de jugador entrante por saliente. Toma la misma posición"""
    for i, player in enumerate(state.players):
        if player.id == player_out_id:
            player_in.x = player.x
            player_in.y = player.y
            state.players[i] = player_in
            return


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

    _resolve_kicks(state, actions, rng)

    _move_players(state, actions)

    _separate_players(state)

    _move_ball(state)

    goal = _check_goal(state)
    if goal is not None:
        events.append(goal)

    _decrease_cooldowns(state)

    state.tick += 1

    return events
