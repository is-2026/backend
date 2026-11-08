from dataclasses import replace

from app.engine.constants import GOALIE_FORMATION, KICKER_FORMATION, PENALTY_TICKS
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
