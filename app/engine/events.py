from dataclasses import dataclass


@dataclass(frozen=True)
class GoalEvent:
    """Mismos campos que el mensaje `goal` de asyncAPI, menos match_id
    (lo va a agregar quien transmita el partido)."""

    tick: int
    player_id: str
    team_id: str
    minute: int
