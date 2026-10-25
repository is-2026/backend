from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

from app.engine.constants import TICKS_PER_MINUTE
from app.engine.events import GoalEvent
from app.engine.state import MatchState
from app.ws.match.pauses import Pause


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


class ClubSummary(BaseModel):
    id: str
    name: str
    avatar_url: str


class LineupPlayer(BaseModel):
    player_id: str
    number: int
    name: str
    is_starter: bool
    power: int
    agility: int
    control: int
    speed: int
    strength: int
    behavior_id: str | None = None  # los suplentes no tienen
    behavior_name: str | None = None


class MatchInfo(BaseModel):
    """Lo que no cambia durante el partido: clubes y alineaciones."""

    home_club: ClubSummary
    away_club: ClubSummary
    home_lineup: list[LineupPlayer]
    away_lineup: list[LineupPlayer]


MatchStatus = Literal["in_progress", "paused", "finished"]


class MatchStartedData(MatchInfo):
    match_id: str
    match_start: datetime
    tick: int
    total_ticks: int
    home_score: int
    away_score: int
    status: MatchStatus = "in_progress"


class MatchStartedMessage(BaseModel):
    type: Literal["matchStarted"] = "matchStarted"
    data: MatchStartedData


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


class MatchFinishedData(BaseModel):
    match_id: str
    tick: int
    home_score: int
    away_score: int
    match_end: datetime
    status: Literal["finished"] = "finished"


class MatchFinishedMessage(BaseModel):
    type: Literal["matchFinished"] = "matchFinished"
    data: MatchFinishedData


class CoolingBreakStartData(BaseModel):
    match_id: str
    tick: int
    cooling_break_number: int
    cooling_break_start: datetime
    ends_at: datetime


class CoolingBreakStartMessage(BaseModel):
    type: Literal["coolingBreakStart"] = "coolingBreakStart"
    data: CoolingBreakStartData


class HalftimeStartData(BaseModel):
    match_id: str
    tick: int
    halftime_start: datetime
    ends_at: datetime


class HalftimeStartMessage(BaseModel):
    type: Literal["halftimeStart"] = "halftimeStart"
    data: HalftimeStartData


class MatchResumedData(BaseModel):
    match_id: str
    tick: int
    resume_type: Literal[
        "after_cooling_break_1", "after_cooling_break_2", "after_halftime"
    ]


class MatchResumedMessage(BaseModel):
    type: Literal["matchResumed"] = "matchResumed"
    data: MatchResumedData


def match_started_message(
    match_id: str,
    info: MatchInfo,
    match_start: datetime,
    state: MatchState,
    status: MatchStatus = "in_progress",
) -> MatchStartedMessage:
    """Lo fijo sale de `info`; tick y marcador, del estado en este momento."""
    return MatchStartedMessage(
        data=MatchStartedData(
            **dict(info),
            match_id=match_id,
            match_start=match_start,
            tick=state.tick,
            total_ticks=state.total_ticks,
            home_score=state.home_score,
            away_score=state.away_score,
            status=status,
        )
    )


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


def match_finished_message(match_id: str, state: MatchState) -> MatchFinishedMessage:
    """Se llama cuando termina el runner de correr los total_ticks"""
    return MatchFinishedMessage(
        data=MatchFinishedData(
            match_id=match_id,
            tick=state.tick,
            home_score=state.home_score,
            away_score=state.away_score,
            match_end=datetime.now(timezone.utc),
        )
    )


def pause_start_message(
    match_id: str, state: MatchState, pause: Pause, seconds: float
) -> CoolingBreakStartMessage | HalftimeStartMessage:
    """Aviso de que empezó pause. seconds es lo que va a durar de verdad"""
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(seconds=seconds)
    if pause == Pause.HALFTIME:
        return HalftimeStartMessage(
            data=HalftimeStartData(
                match_id=match_id,
                tick=state.tick,
                halftime_start=now,
                ends_at=ends_at,
            )
        )
    else:
        return CoolingBreakStartMessage(
            data=CoolingBreakStartData(
                match_id=match_id,
                tick=state.tick,
                cooling_break_number=1 if pause == Pause.COOLING_BREAK_1 else 2,
                cooling_break_start=now,
                ends_at=ends_at,
            )
        )


def match_resumed_message(
    match_id: str, state: MatchState, pause: Pause
) -> MatchResumedMessage:
    """Aviso de que terminó pause. El tick es el mismo del inicio"""
    return MatchResumedMessage(
        data=MatchResumedData(
            match_id=match_id,
            tick=state.tick,
            resume_type=f"after_{pause}",
        )
    )
