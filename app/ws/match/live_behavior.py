from app.engine.state import MatchState, Side
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

def update_info_match(
        info : MatchInfo, team_id: str, player_id: str, behavior_id: str, behavior_name: str
)-> None:
    side = get_side(team_id, info)
    if side is Side.HOME: 
        lineup = info.home_lineup
    else:
        lineup = info.away_lineup

    info_player = next(p for p in lineup if p.player_id == player_id) #busco el jugador en la lista de LineupPlayer
    info_player.behavior_id = behavior_id
    info_player.behavior_name = behavior_name