from dataclasses import replace

from app.engine.constants import GOALIE_FORMATION, KICKER_FORMATION, PENALTY_TICKS
from app.engine.engine import kickoff
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
