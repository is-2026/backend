from typing import Literal

from pydantic import BaseModel

from app.engine.events import GoalEvent
from app.engine.state import MatchState
from app.engine.constants import TICKS_PER_MINUTE


class Position(BaseModel):
    x: float
    y: float


class PlayerPosition(BaseModel):
    player_id: str
    position: Position


class MatchStateData(BaseModel):
    match_id: str
    tick: int
    players: list[PlayerPosition]
    ball_position: Position


class MatchStateMessage(BaseModel):
    type: Literal["matchState"] = "matchState"
    data: MatchStateData


class GoalData(BaseModel):
    match_id: str
    tick: int
    player_id: str
    team_id: str
    minute: int
    home_score: int
    away_score: int


class GoalMessage(BaseModel):
    type: Literal["goal"] = "goal"
    data: GoalData


def match_state_message(match_id: str, state: MatchState) -> MatchStateMessage:
    """Arma el matchState desde el estado del motor (ya está en coordenadas absolutas)."""
    players = [
        PlayerPosition(player_id=p.id, position=Position(x=p.x, y=p.y))
        for p in state.players
    ]
    data = MatchStateData(
        match_id=match_id,
        tick=state.tick,
        players=players,
        ball_position=Position(x=state.ball.x, y=state.ball.y),
    )
    return MatchStateMessage(data=data)


def goal_message(match_id: str, event: GoalEvent, state: MatchState) -> GoalMessage:
    """Se llama después del step: el marcador de `state` ya tiene sumado el gol,
    y el tick sale de state.tick (event.tick es el de antes de incrementar)."""
    return GoalMessage(
        data=GoalData(
            match_id=match_id,
            tick=state.tick,
            player_id=event.player_id,
            team_id=event.team_id,
            minute=state.tick // TICKS_PER_MINUTE,
            home_score=state.home_score,
            away_score=state.away_score,
        )
    )
