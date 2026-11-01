from pydantic import BaseModel


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
