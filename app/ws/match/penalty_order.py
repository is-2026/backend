from typing import TYPE_CHECKING

from app.engine.state import PlayerState, Side
from app.ws.match.info import MatchInfo
from app.ws.match.substitutions import get_side

if TYPE_CHECKING:
    from app.ws.match.runner import LiveMatch


class InvalidPenaltyOrder(Exception):
    """Hay pateadores repetidos o que no son de los 6 convocados del club"""


def build_penalty_order(
    info: MatchInfo, team_id: str, player_ids: list[str]
) -> list[PlayerState]:
    """Los pateadores del club en ese orden, armados desde los convocados.
    Tira InvalidPenaltyOrder si hay repetidos o alguno no es convocado."""
    if len(set(player_ids)) != len(player_ids):
        raise InvalidPenaltyOrder("Hay pateadores repetidos")
    side = get_side(team_id, info)
    lineup = info.home_lineup if side == Side.HOME else info.away_lineup
    squad = {p.player_id: p for p in lineup}
    if any(player_id not in squad for player_id in player_ids):
        raise InvalidPenaltyOrder("Hay pateadores que no son convocados del club")
    return [
        PlayerState(
            id=player_id,
            side=side,
            power=squad[player_id].power,
            agility=squad[player_id].agility,
            control=squad[player_id].control,
            speed=squad[player_id].speed,
            strength=squad[player_id].strength,
        )
        for player_id in player_ids
    ]


def load_penalty_order(
    live: "LiveMatch", team_id: str, kickers: list[PlayerState], codes: list[str]
) -> None:
    # se cargan ya, asi el hijo los tiene listos cuando arranca la tanda
    for player, code in zip(kickers, codes, strict=True):
        live.executor.set_player_behavior(player, code)
    live.penalty_orders[team_id] = kickers
