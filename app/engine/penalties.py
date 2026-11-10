import random
from dataclasses import replace
from math import hypot

from app.engine.actions import Action, Move, Shoot
from app.engine.constants import (
    GOAL_HALF_WIDTH,
    GOALIE_CORRECTION_SPEED_PCT,
    GOALIE_FORMATION,
    GOALIE_LINE_X,
    GOALIE_REACTION_DISTANCE,
    GOALIE_STOP_DISTANCE,
    KICKER_FORMATION,
    MAX_PENALTIES,
    PENALTIES_PER_TEAM,
    PENALTY_TICKS,
)
from app.engine.engine import control_radius, kickoff
from app.engine.events import GoalEvent
from app.engine.state import MatchState, PlayerState, Side


def penalty_state(
    home_team_id: str,
    away_team_id: str,
    kicker: PlayerState,
    goalie: PlayerState,
    home_penalties: int = 0,
    away_penalties: int = 0,
) -> MatchState:
    kicker_c = replace(kicker, cooldown=0)
    goalie_c = replace(goalie, cooldown=0)
    if kicker.side == Side.HOME:
        home_formation, away_formation = KICKER_FORMATION, GOALIE_FORMATION
    else:
        home_formation, away_formation = GOALIE_FORMATION, KICKER_FORMATION
    state = MatchState(
        home_team_id=home_team_id,
        home_formation=home_formation,
        away_team_id=away_team_id,
        away_formation=away_formation,
        players=[kicker_c, goalie_c],
        total_ticks=PENALTY_TICKS,
        home_score=home_penalties,
        away_score=away_penalties,
    )
    kickoff(state)
    return state


def kick_scored(events: list[GoalEvent]) -> bool:
    """Devuelve si hubo un gol"""
    return len(events) >= 1


def kick_stopped(state: MatchState, goalie: PlayerState) -> bool:
    """Se llama después de kick_scored()"""
    return (
        state.ball.last_touch_id == goalie.id
        or (state.ball.x < 0 if goalie.side == Side.AWAY else state.ball.x > 0)
        or state.tick >= state.total_ticks
    )


class Goalie:
    """El arquero de la tanda: lo maneja el sistema, no el comportamiento del jugador.
    Cuando rematan se tira a un palo elegido al azar y, cuando la pelota se le acerca,
    va hacia ella para corregir si eligió mal. Si le llega a su radio, la despeja."""

    def __init__(self, player: PlayerState, rng: random.Random):
        self._id = player.id
        # el local defiende el arco de -x y el visitante el de +x
        self._sign = 1 if player.side == Side.HOME else -1
        self._dive_y = rng.choice((-GOAL_HALF_WIDTH, GOAL_HALF_WIDTH))

    def action(self, state: MatchState) -> Action:
        me = next(p for p in state.players if p.id == self._id)
        ball = state.ball
        distance = hypot(ball.x - me.x, ball.y - me.y)
        if distance <= control_radius(me.control):
            return Shoot(self._sign, 0.0, 100)  # la despeja hacia la mitad del pateador
        if ball.last_touch_id is None:
            return Move(0.0, 0.0, 0)  # todavía no remataron
        if distance <= GOALIE_REACTION_DISTANCE:
            # la ve venir: corrige hacia la pelota, más lento
            target_y, speed = ball.y, GOALIE_CORRECTION_SPEED_PCT
        else:
            target_y, speed = self._dive_y, 100  # se tira al palo que eligió
        dx, dy = self._sign * GOALIE_LINE_X - me.x, target_y - me.y
        if hypot(dx, dy) <= GOALIE_STOP_DISTANCE:
            return Move(0.0, 0.0, 0)  # ya llegó: se queda quieto, como el Defensor
        return Move(dx, dy, speed)


class Shootout:
    def __init__(
        self,
        home_kickers: list[PlayerState],
        away_kickers: list[PlayerState],
        rng: random.Random,
    ):
        for kickers in (home_kickers, away_kickers):
            if len(kickers) != PENALTIES_PER_TEAM:
                raise ValueError(f"Cada club patea con {PENALTIES_PER_TEAM} jugadores")
        self._kickers = {Side.HOME: home_kickers, Side.AWAY: away_kickers}
        self._rng = rng
        self._taken = 0  # penales pateados entre los dos
        self.home_penalties = 0
        self.away_penalties = 0
        self.winner: Side | None = None

    @property
    def finished(self) -> bool:
        return self.winner is not None

    def _kicking_side(self) -> Side:
        # patea primero el local (par) y luego alternan
        return Side.HOME if self._taken % 2 == 0 else Side.AWAY

    def next_kick(self) -> tuple[Side, PlayerState, PlayerState]:
        side = self._kicking_side()
        rival = Side.AWAY if side == Side.HOME else Side.HOME
        # en la muerte súbita se repite el orden desde el primero
        number = (self._taken // 2) % PENALTIES_PER_TEAM
        # el arquero del penal i es el pateador i del rival
        return side, self._kickers[side][number], self._kickers[rival][number]

    def record(self, scored: bool) -> None:
        if self.finished:
            return  # ya termino no toco nada
        if scored:
            if self._kicking_side() == Side.HOME:
                self.home_penalties += 1
            else:
                self.away_penalties += 1
        self._taken += 1
        self._check_winner()

    def _check_winner(self) -> None:
        home_taken = (self._taken + 1) // 2
        away_taken = self._taken // 2
        round_kicks = max(PENALTIES_PER_TEAM, home_taken, away_taken)
        if self.home_penalties + round_kicks - home_taken < self.away_penalties:
            self.winner = Side.AWAY
        elif self.away_penalties + round_kicks - away_taken < self.home_penalties:
            self.winner = Side.HOME
        elif self._taken >= MAX_PENALTIES:
            self.winner = self._rng.choice([Side.HOME, Side.AWAY])
