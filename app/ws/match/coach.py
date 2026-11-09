import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.engine.behavior_exec import CoachSnapshot
from app.engine.coach_orders import CoachOrder, PenaltyOrder, SetBehavior, Substitute
from app.engine.state import Side
from app.ws.match.info import LineupPlayer, MatchInfo
from app.ws.match.live_behavior import (
    PlayerNotOnField,
    update_info_match,
    validate_player_on_field,
)
from app.ws.match.messages import behavior_changed_message
from app.ws.match.penalty_order import (
    InvalidPenaltyOrder,
    build_penalty_order,
    load_penalty_order,
)
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

if TYPE_CHECKING:  # si lo importo normal queda circular con runner
    from app.ws.match.runner import LiveMatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClubBehavior:
    name: str
    code: str


@dataclass(frozen=True)
class CoachSetup:
    code: str
    behaviors: dict[str, ClubBehavior]  # behavior_id -> comportamiento de jugador


def _team_id(side: Side, info: MatchInfo) -> str:
    return info.home_club.id if side == Side.HOME else info.away_club.id


def _lineup(side: Side, info: MatchInfo) -> list[LineupPlayer]:
    return info.home_lineup if side == Side.HOME else info.away_lineup


def coach_codes(coaches: dict[str, CoachSetup], info: MatchInfo) -> dict[Side, str]:
    return {get_side(team_id, info): setup.code for team_id, setup in coaches.items()}


def coach_snapshot(
    live: "LiveMatch", team_id: str, penalty_shootout: bool = False
) -> CoachSnapshot:
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


def coach_snapshots(
    live: "LiveMatch", penalty_shootout: bool = False
) -> dict[Side, CoachSnapshot]:
    return {
        get_side(team_id, live.info): coach_snapshot(live, team_id, penalty_shootout)
        for team_id in live.coaches
    }


def _apply_set_behavior(
    live: "LiveMatch", team_id: str, order: SetBehavior
) -> dict | None:
    """Devuelve el mensaje behaviorChanged, o None si no se hizo el cambio"""
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
        return None  # ya lo tiene

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
    behavior = live.coaches[team_id].behaviors.get(order.behavior_id)
    if behavior is None:
        logger.debug("DT de %s: el comportamiento %s no es del club", team_id, order)
        return
    try:
        window = substitution_window(False, live.pauses_started)  # nunca en pausa
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
    """Aplica las ordenes del tick y devuelve los mensajes para mandar"""
    messages = []
    for side, team_orders in orders.items():
        team_id = _team_id(side, live.info)
        if team_id not in live.coaches:
            continue
        for order in team_orders:
            try:
                if isinstance(order, SetBehavior):
                    message = _apply_set_behavior(live, team_id, order)
                    if message is not None:
                        messages.append(message)
                elif isinstance(order, Substitute):
                    _apply_substitute(live, team_id, order)
            except ClubNotInMatch:
                logger.warning("El DT de %s no juega este partido", team_id)
    return messages


def _apply_penalty_order(live: "LiveMatch", team_id: str, order: PenaltyOrder) -> None:
    # si no es valido no hago nada y patean los de por defecto
    behaviors = live.coaches[team_id].behaviors
    codes = []
    for _, behavior_id in order.kickers:
        behavior = behaviors.get(behavior_id)
        if behavior is None:
            logger.debug("DT de %s: comportamiento ajeno en %s", team_id, order)
            return
        codes.append(behavior.code)
    try:
        kickers = build_penalty_order(
            live.info, team_id, [player_id for player_id, _ in order.kickers]
        )
    except InvalidPenaltyOrder as e:
        logger.debug("DT de %s: orden de penales ignorado (%s)", team_id, e)
        return
    load_penalty_order(live, team_id, kickers, codes)


def apply_penalty_orders(
    live: "LiveMatch", orders: dict[Side, list[CoachOrder]]
) -> None:
    for side, team_orders in orders.items():
        team_id = _team_id(side, live.info)
        if team_id not in live.coaches:
            continue
        for order in team_orders:
            if isinstance(order, PenaltyOrder):
                _apply_penalty_order(live, team_id, order)
