import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.engine.behavior_exec import CoachSnapshot
from app.engine.coach_orders import CoachOrder, SetBehavior, Substitute
from app.engine.state import Side
from app.ws.match.info import LineupPlayer, MatchInfo
from app.ws.match.live_behavior import (
    PlayerNotOnField,
    update_info_match,
    validate_player_on_field,
)
from app.ws.match.messages import behavior_changed_message
from app.ws.match.substitutions import (
    ClubNotInMatch,
    InvalidSubstitution,
    PendingSubstitution,
    SubstitutionConflict,
    get_side,
    schedule,
    substitution_window,
    validate_players,
)

if TYPE_CHECKING:
    # solo para los tipos: el runner importa este módulo
    from app.ws.match.runner import LiveMatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClubBehavior:
    """Comportamiento de jugador del club, cargado al arrancar el partido."""
    name: str
    code: str


@dataclass(frozen=True)
class CoachSetup:
    """El DT de un club en un partido: se arma al arrancar y no cambia aunque el
    club active o quite su DT durante el partido."""

    code: str
    # behavior_id -> comportamiento: los únicos que el DT puede asignar
    behaviors: dict[str, ClubBehavior]


def _team_id(side: Side, info: MatchInfo) -> str:
    return info.home_club.id if side == Side.HOME else info.away_club.id


def _lineup(side: Side, info: MatchInfo) -> list[LineupPlayer]:
    return info.home_lineup if side == Side.HOME else info.away_lineup


def coach_codes(coaches: dict[str, CoachSetup], info: MatchInfo) -> dict[Side, str]:
    """team_id -> DT pasa a lado -> código del DT, que es lo que pide el executor."""
    return {get_side(team_id, info): setup.code for team_id, setup in coaches.items()}


def coach_snapshot(
    live: "LiveMatch", team_id: str, penalty_shootout: bool = False
) -> CoachSnapshot:
    """La foto que ve el DT del club en este momento del partido."""
    side = get_side(team_id, live.info)
    state = live.state
    lineup = _lineup(side, live.info)
    behavior_of = {p.player_id: p.behavior_id for p in lineup}
    on_field_ids = [p.id for p in state.players if p.side == side]

    if side == Side.HOME:
        own_score, rival_score = state.home_score, state.away_score
    else:
        own_score, rival_score = state.away_score, state.home_score

    return CoachSnapshot(
        own_score=own_score,
        rival_score=rival_score,
        tick=state.tick,
        total_ticks=state.total_ticks,
        on_field=tuple(
            (player_id, behavior_of.get(player_id) or "") for player_id in on_field_ids
        ),
        bench=tuple(p.player_id for p in lineup if p.player_id not in on_field_ids),
        behaviors=tuple(
            (behavior_id, behavior.name)
            for behavior_id, behavior in live.coaches[team_id].behaviors.items()
        ),
        penalty_shootout=penalty_shootout,
    )


def coach_snapshots(live: "LiveMatch") -> dict[Side, CoachSnapshot]:
    """Las fotos de los DT del partido, por lado. Un club sin DT no aparece."""
    return {
        get_side(team_id, live.info): coach_snapshot(live, team_id)
        for team_id in live.coaches
    }


def _apply_set_behavior(
    live: "LiveMatch", team_id: str, order: SetBehavior
) -> dict | None:
    """Cambia el comportamiento del jugador. Devuelve el behaviorChanged para mandar,
    o None si la orden no es válida o el jugador ya tenía ese comportamiento."""
    behavior = live.coaches[team_id].behaviors.get(order.behavior_id)
    if behavior is None:
        logger.debug("DT de %s: el comportamiento %s no es del club", team_id, order)
        return None
    try:
        validate_player_on_field(live.state, live.info, team_id, order.player_id)
    except PlayerNotOnField:
        logger.debug("DT de %s: el jugador no está en cancha (%s)", team_id, order)
        return None

    lineup = _lineup(get_side(team_id, live.info), live.info)
    current = next(p for p in lineup if p.player_id == order.player_id)
    if current.behavior_id == order.behavior_id:
        return None  # ya lo tiene: no lo recargo en el hijo

    # se carga ahora, entre este tick y el siguiente: rige desde el próximo tick
    live.executor.set_behavior(order.player_id, behavior.code)
    update_info_match(
        live.info, team_id, order.player_id, order.behavior_id, behavior.name
    )
    message = behavior_changed_message(
        str(live.match_id),
        live.state,
        order.player_id,
        order.behavior_id,
        behavior.name,
    )
    return message.model_dump(mode="json")


def _apply_substitute(live: "LiveMatch", team_id: str, order: Substitute) -> None:
    """Programa la sustitución para la próxima pausa, igual que el endpoint."""
    behavior = live.coaches[team_id].behaviors.get(order.behavior_id)
    if behavior is None:
        logger.debug("DT de %s: el comportamiento %s no es del club", team_id, order)
        return
    try:
        # el DT solo corre mientras se juega: nunca está en una pausa
        window = substitution_window(False, live.pauses_started)
        validate_players(
            live.state, live.info, team_id, order.player_out_id, order.player_in_id
        )
        sub = PendingSubstitution(
            id=str(uuid.uuid4()),
            player_out_id=order.player_out_id,
            player_in_id=order.player_in_id,
            behavior_id=order.behavior_id,
            behavior_name=behavior.name,
            behavior_code=behavior.code,
            window=window,
        )
        schedule(live.pending_substitutions, team_id, sub)
    except (InvalidSubstitution, SubstitutionConflict) as e:
        logger.debug("DT de %s: sustitución ignorada (%s)", team_id, e)


def apply_coach_orders(
    live: "LiveMatch", orders: dict[Side, list[CoachOrder]]
) -> list[dict]:
    """Valida y aplica las órdenes de los DT de este tick.
    Devuelve los mensajes para mandar por el websocket (behaviorChanged)."""
    messages = []
    for side, team_orders in orders.items():
        team_id = _team_id(side, live.info)
        if team_id not in live.coaches:
            continue  # ese club no tiene DT en este partido
        for order in team_orders:
            try:
                if isinstance(order, SetBehavior):
                    message = _apply_set_behavior(live, team_id, order)
                    if message is not None:
                        messages.append(message)
                elif isinstance(order, Substitute):
                    _apply_substitute(live, team_id, order)
                # el PenaltyOrder no llega durante el juego (el DT lo ignora)
            except ClubNotInMatch:
                logger.warning("El DT de %s no juega este partido", team_id)
    return messages
