import random
from dataclasses import replace

from app.engine.constants import (
    GOALIE_FORMATION,
    KICKER_FORMATION,
    MAX_PENALTIES,
    PENALTIES_PER_TEAM,
    PENALTY_TICKS,
)
from app.engine.engine import kickoff
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
