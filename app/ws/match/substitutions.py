from dataclasses import dataclass

from app.engine.engine import change_player
from app.engine.executor import BehaviorExecutor
from app.engine.state import MatchState, PlayerState, Side
from app.ws.match.messages import MatchInfo
from app.ws.match.pauses import Pause


@dataclass
class PendingSubstitution:
    id: str
    player_out_id: str
    player_in_id: str
    behavior_id: str
    behavior_name: str
    behavior_code: str
    window: Pause


class InvalidSubstitution(Exception):
    """Sustitución inválida"""


class SubstitutionConflict(Exception):
    """No quedan más sustituciones o ya hay una sustitución programada"""


class NoPendingSubstitution(Exception):
    """No hay una sustitución pendiente para eliminar"""


class ClubNotInMatch(Exception):
    """El equipo no juega este partido"""


def substitution_window(in_pause: bool, pauses_started: int) -> Pause:
    """La pausa en curso si in_pause, si no la próxima.
    Tira SubstitutionConflict si ya no quedan."""
    if pauses_started >= 3 and not in_pause:
        raise SubstitutionConflict("No quedan más ventanas de cambios")
    pauses = list(Pause)
    if in_pause:
        pause = pauses[pauses_started - 1]
    else:
        pause = pauses[pauses_started]
    return pause


def get_side(team_id: str, info: MatchInfo) -> Side:
    """El lado del club en el partido. Tira ClubNotInMatch si no juega"""
    if team_id == info.home_club.id:
        return Side.HOME
    if team_id == info.away_club.id:
        return Side.AWAY
    raise ClubNotInMatch(f"El club {team_id} no juega este partido")


def _team_players_on_field(side: Side, state: MatchState) -> list[str]:
    return [p.id for p in state.players if p.side == side]


def _team_squad(side: Side, info: MatchInfo) -> list[str]:
    lineup = info.home_lineup if side == Side.HOME else info.away_lineup
    return [p.player_id for p in lineup]


def validate_players(
    state: MatchState,
    info: MatchInfo,
    team_id: str,
    player_out_id: str,
    player_in_id: str,
) -> None:
    """Tira InvalidSubstitution si el que sale no está en cancha de ese club
    o si el que entra no está en su banco."""
    side = get_side(team_id, info)
    on_field = _team_players_on_field(side, state)
    squad = _team_squad(side, info)
    bench = [p for p in squad if p not in on_field]
    if player_in_id not in bench:
        raise InvalidSubstitution(
            "El jugador ingresante no está en el banco de suplentes"
        )
    if player_out_id not in on_field:
        raise InvalidSubstitution("El jugador saliente no está en la cancha")


def schedule(
    pending: dict[str, PendingSubstitution],
    team_id: str,
    substitution: PendingSubstitution,
) -> None:
    """Tira SubstitutionConflict si el club ya tiene una pendiente; si no, la guarda."""
    if team_id in pending:
        raise SubstitutionConflict("Ya hay una sustitución programada")
    pending[team_id] = substitution


def cancel(
    pending: dict[str, PendingSubstitution], team_id: str
) -> PendingSubstitution:
    """Saca la del club y la devuelve. Tira NoPendingSubstitution si no tenía."""
    sub = pending.pop(team_id, None)
    if sub is None:
        raise NoPendingSubstitution("No hay sustituciones pendientes para borrar")
    return sub


def execute_substitution(
    state: MatchState,
    info: MatchInfo,
    executor: BehaviorExecutor,
    team_id: str,
    sub: PendingSubstitution,
) -> None:
    side = get_side(team_id, info)
    lineup = info.home_lineup if side == Side.HOME else info.away_lineup
    player_info = next(p for p in lineup if p.player_id == sub.player_in_id)
    player_in_state = PlayerState(
        id=sub.player_in_id,
        side=side,
        power=player_info.power,
        agility=player_info.agility,
        control=player_info.control,
        speed=player_info.speed,
        strength=player_info.strength,
    )
    change_player(state, sub.player_out_id, player_in_state)
    executor.set_behavior(sub.player_in_id, sub.behavior_code)
