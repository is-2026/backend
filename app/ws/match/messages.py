from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel

from app.engine.constants import TICKS_PER_MINUTE
from app.engine.events import GoalEvent
from app.engine.penalties import Shootout
from app.engine.state import MatchState, Side
from app.ws.match.info import MatchInfo
from app.ws.match.pauses import Pause
from app.ws.match.substitutions import PendingSubstitution


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


MatchStatus = Literal["in_progress", "paused", "penalties", "finished"]


class MatchStartedData(MatchInfo):
    match_id: str
    match_start: datetime
    tick: int
    total_ticks: int
    home_score: int
    away_score: int
    status: MatchStatus = "in_progress"
    # solo durante la definición por penales
    home_penalties: int | None = None
    away_penalties: int | None = None


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
    home_penalties: int | None = None
    away_penalties: int | None = None
    winner_club_id: str | None = None
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


class SubstitutionMadeData(BaseModel):
    match_id: str
    tick: int
    player_in_id: str
    player_out_id: str
    behavior_id: str | None = None
    behavior_name: str | None = None


class SubstitutionMadeMessage(BaseModel):
    type: Literal["substitutionMade"] = "substitutionMade"
    data: SubstitutionMadeData


class BehaviorChangedData(BaseModel):
    match_id: str
    tick: int
    player_id: str
    behavior_id: str
    behavior_name: str


class BehaviorChangedMessage(BaseModel):
    type: Literal["behaviorChanged"] = "behaviorChanged"
    data: BehaviorChangedData


class PenaltyShootoutStartData(BaseModel):
    match_id: str
    ends_at: datetime


class PenaltyShootoutStartMessage(BaseModel):
    type: Literal["penaltyShootoutStart"] = "penaltyShootoutStart"
    data: PenaltyShootoutStartData


class PenaltyKickData(BaseModel):
    match_id: str
    number: int
    team_id: str
    kicker_id: str
    defender_id: str
    penalty_ticks: int


class PenaltyKickMessage(BaseModel):
    type: Literal["penaltyKick"] = "penaltyKick"
    data: PenaltyKickData


class PenaltyResultData(BaseModel):
    match_id: str
    number: int
    team_id: str
    scored: bool
    home_penalties: int
    away_penalties: int


class PenaltyResultMessage(BaseModel):
    type: Literal["penaltyResult"] = "penaltyResult"
    data: PenaltyResultData


def match_started_message(
    match_id: str,
    info: MatchInfo,
    match_start: datetime,
    state: MatchState,
    status: MatchStatus = "in_progress",
    home_penalties: int | None = None,
    away_penalties: int | None = None,
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
            home_penalties=home_penalties,
            away_penalties=away_penalties,
        )
    )


def match_state_message(
    match_id: str, state: MatchState, mirrored: bool = False
) -> MatchStateMessage:
    """Arma el matchState desde el estado del motor (ya está en coordenadas absolutas).
    Con mirrored da vuelta la cancha (x, y) -> (-x, -y), igual que el motor con el visitante:
    en la tanda, así los penales del visitante también se ven en el arco derecho."""
    k = -1 if mirrored else 1
    players = [
        PlayerPosition(player_id=p.id, position=Position(x=k * p.x, y=k * p.y))
        for p in state.players
    ]
    data = MatchStateData(
        match_id=match_id,
        tick=state.tick,
        players=players,
        ball_position=Position(x=k * state.ball.x, y=k * state.ball.y),
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


def _winner_club_id(state: MatchState, shootout: Shootout | None) -> str | None:
    """El ganador por goles, o por penales si hubo tanda. None si terminó empatado."""
    if state.home_score != state.away_score:
        home_won = state.home_score > state.away_score
    elif shootout is not None and shootout.winner is not None:
        home_won = shootout.winner == Side.HOME
    else:
        return None
    return state.home_team_id if home_won else state.away_team_id


def match_finished_message(
    match_id: str, state: MatchState, shootout: Shootout | None = None
) -> MatchFinishedMessage:
    """Se llama cuando termina el runner de correr los total_ticks
    ( y la tanda de penales si es que hubo)
    """
    return MatchFinishedMessage(
        data=MatchFinishedData(
            match_id=match_id,
            tick=state.tick,
            home_score=state.home_score,
            away_score=state.away_score,
            match_end=datetime.now(timezone.utc),
            home_penalties=shootout.home_penalties if shootout else None,
            away_penalties=shootout.away_penalties if shootout else None,
            winner_club_id=_winner_club_id(state, shootout),
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


def substitution_made_message(
    match_id: str,
    state: MatchState,
    sub: PendingSubstitution,
) -> SubstitutionMadeMessage:
    return SubstitutionMadeMessage(
        data=SubstitutionMadeData(
            match_id=match_id,
            tick=state.tick,
            player_in_id=sub.player_in_id,
            player_out_id=sub.player_out_id,
            behavior_id=sub.behavior_id,
            behavior_name=sub.behavior_name,
        )
    )


def behavior_changed_message(
    match_id: str,
    state: MatchState,
    player_id: str,
    behavior_id: str,
    behavior_name: str,
) -> BehaviorChangedMessage:
    return BehaviorChangedMessage(
        data=BehaviorChangedData(
            match_id=match_id,
            tick=state.tick,
            player_id=player_id,
            behavior_id=behavior_id,
            behavior_name=behavior_name,
        )
    )


def penalty_shootout_start_message(
    match_id: str, seconds: float
) -> PenaltyShootoutStartMessage:
    ends_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return PenaltyShootoutStartMessage(
        data=PenaltyShootoutStartData(match_id=match_id, ends_at=ends_at)
    )


def penalty_kick_message(
    match_id: str,
    number: int,
    team_id: str,
    kicker_id: str,
    defender_id: str,
    penalty_ticks: int,
) -> PenaltyKickMessage:
    return PenaltyKickMessage(
        data=PenaltyKickData(
            match_id=match_id,
            number=number,
            team_id=team_id,
            kicker_id=kicker_id,
            defender_id=defender_id,
            penalty_ticks=penalty_ticks,
        )
    )


def penalty_result_message(
    match_id: str, number: int, team_id: str, scored: bool, shootout: Shootout
) -> PenaltyResultMessage:
    return PenaltyResultMessage(
        data=PenaltyResultData(
            match_id=match_id,
            number=number,
            team_id=team_id,
            scored=scored,
            home_penalties=shootout.home_penalties,
            away_penalties=shootout.away_penalties,
        )
    )
