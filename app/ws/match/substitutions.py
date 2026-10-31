from dataclasses import dataclass

from app.ws.match.pauses import Pause


@dataclass
class PendingSubstitution:
    id: str
    player_in_id: str
    player_out_id: str
    behavior_id: str
    behavior_name: str
    behavior_code: str
    window: Pause
