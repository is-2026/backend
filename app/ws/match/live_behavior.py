from app.engine.state import MatchState
from app.ws.match.info import MatchInfo
from app.ws.match.substitutions import _team_players_on_field, get_side


class PlayerNotOnField(Exception):
    """El jugador no se encuentra en cancha del lado del club"""


def validate_player_on_field(
    state: MatchState, info: MatchInfo, team_id: str, player_id: str
) -> None:
    side = get_side(team_id, info)
    if player_id not in _team_players_on_field(side, state):  #team_player da una lista de str de los jugadires que estan de ese lado de la cancha
        raise PlayerNotOnField("El jugador no se encuentra en cancha del lado del club")