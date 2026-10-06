from dataclasses import dataclass, field
from enum import StrEnum


class Side(StrEnum):  # con StrEnum para que sea más fácil serializar
    HOME = "home"
    AWAY = "away"


@dataclass
class PlayerState:
    id: str
    side: Side
    # PACSS
    power: int
    agility: int
    control: int
    speed: int
    strength: int
    # posición
    x: float = 0.0
    y: float = 0.0
    cooldown: int = 0  # ticks que faltan para poder volver a patear


@dataclass
class BallState:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    last_touch_id: str | None = None  # para atribuir el gol


Position = tuple[float, float]
Formation = tuple[Position, Position, Position]


@dataclass
class MatchState:
    home_team_id: str
    home_formation: Formation
    away_team_id: str
    away_formation: Formation
    players: list[PlayerState]
    total_ticks: int
    ball: BallState = field(default_factory=BallState)
    tick: int = 0
    home_score: int = 0
    away_score: int = 0
