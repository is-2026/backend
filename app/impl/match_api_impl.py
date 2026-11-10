import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.match_api_base import BaseMatchApi
from app.db.match import MatchDB
from app.models.match import Match
from app.models.substitution import Substitution
from app.models.change_live_behavior_request import ChangeLiveBehaviorRequest
from app.repositories.behavior_repository import BehaviorRepository
from app.repositories.match_repository import MatchRepository
from app.ws.connection_manager import ConnectionManager
from app.ws.match.runner import LiveMatch, Phase, live_matches, match_connections
from app.ws.match.substitutions import (
    ClubNotInMatch,
    InvalidSubstitution,
    NoPendingSubstitution,
    PendingSubstitution,
    SubstitutionConflict,
    cancel,
    get_side,
    schedule,
    substitution_window,
    validate_players,
)
from app.ws.match.live_behavior import validate_player_on_field, PlayerNotOnField, update_info_match
from app.ws.match.messages import behavior_changed_message
from app.models.penalty_order_input import PenaltyOrderInput
from app.ws.match.penalty_order import (
    InvalidPenaltyOrder,
    build_penalty_order,
    load_penalty_order,
)


def _to_match(match_db: MatchDB) -> Match:
    return Match(
        id=match_db.id,
        league_id=match_db.league_id,
        round_number=match_db.round_number,
        home_club_id=match_db.home_club_id,
        home_club_name=match_db.home_club.club_name if match_db.home_club else None,
        away_club_id=match_db.away_club_id,
        away_club_name=match_db.away_club.club_name if match_db.away_club else None,
        status=match_db.status.value,
        home_score=match_db.home_score,
        away_score=match_db.away_score,
        home_penalties=match_db.home_penalties,
        away_penalties=match_db.away_penalties,
    )



def _coach_in_match(live: LiveMatch, team_id: str) -> None:
    if team_id in live.coaches:
        raise HTTPException(
            status_code=409, detail="El club tiene un DT a cargo del partido"
        )


class MatchApiImpl(BaseMatchApi):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_match(self, match_id: uuid.UUID) -> Match:
        # buscamos el partido en la db
        match_db = await MatchRepository(self._session).get_by_id(match_id)
        if not match_db:
            raise HTTPException(status_code=404, detail="El partido no existe")
        # mapeamos al modelo pydantic
        return _to_match(match_db)


    async def change_live_behavior(
        self,
        match_id: uuid.UUID,
        player_id: uuid.UUID,
        change_live_behavior_request: ChangeLiveBehaviorRequest,
        club_id: uuid.UUID,
    ) -> None:
        live = live_matches.get(match_id)
        if live is None:
            raise HTTPException(status_code=404, detail="El partido no está en juego")

        team_id = str(club_id)
        try:
            get_side(team_id, live.info)
        except ClubNotInMatch as e:
            raise HTTPException(
                status_code=403, detail="El club no juega este partido"
            ) from e

        _coach_in_match(live, team_id)

        if live.phase == Phase.PENALTIES:
            raise HTTPException(
                status_code=409, detail="El partido se encuentra en penales"
            )
        player = str(player_id)

        try:
            validate_player_on_field(live.state, live.info, team_id, player)
        except PlayerNotOnField as exc_info:
            raise HTTPException(status_code=404, detail=str(exc_info)) from exc_info

        behavior = await BehaviorRepository(self._session).get_id_and_club(
            change_live_behavior_request.behavior_id, club_id
        )
        if behavior is None or behavior.kind != "player":
            raise HTTPException(status_code=400, detail="El comportamiento no existe")

        live.executor.set_behavior(player, behavior.code)
        update_info_match(live.info, team_id, player, str(behavior.id), behavior.name)

        message = behavior_changed_message(str(match_id), live.state, player ,str(behavior.id), behavior.name ) #armo el mensaje
        await match_connections.broadcast(live.match_id, message.model_dump(mode = "json")) #mando el mensaje a todos los clientes conectados al canal
        #convierto el modelo en un dict para poder dsp pasarlo a json, porque broadcast recibe un dict no un modelo.

    async def schedule_substitution(
        self, match_id, schedule_substitution_input, club_id
    ) -> Substitution:
        live = live_matches.get(match_id)
        if live is None:
            raise HTTPException(status_code=404, detail="El partido no está en juego")

        team_id = str(club_id)
        try:
            get_side(team_id, live.info)
        except ClubNotInMatch as e:
            raise HTTPException(
                status_code=403, detail="El club no juega este partido"
            ) from e

        _coach_in_match(live, team_id)

        behavior = await BehaviorRepository(self._session).get_id_and_club(
            schedule_substitution_input.substitution_behavior_id, club_id
        )
        if behavior is None or behavior.kind != "player":
            raise HTTPException(status_code=400, detail="El comportamiento no existe")

        player_out_id = str(schedule_substitution_input.player_out_id)
        player_in_id = str(schedule_substitution_input.player_in_id)
        try:
            window = substitution_window(
                live.phase == Phase.PAUSED, live.pauses_started
            )
            validate_players(
                live.state, live.info, team_id, player_out_id, player_in_id
            )
            sub = PendingSubstitution(
                id=str(uuid.uuid4()),
                player_out_id=player_out_id,
                player_in_id=player_in_id,
                behavior_id=str(behavior.id),
                behavior_name=behavior.name,
                behavior_code=behavior.code,
                window=window,
            )
            schedule(live.pending_substitutions, team_id, sub)
        except InvalidSubstitution as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except SubstitutionConflict as e:
            raise HTTPException(status_code=409, detail=str(e)) from e

        return Substitution(
            id=sub.id,
            player_out_id=sub.player_out_id,
            player_in_id=sub.player_in_id,
            window=sub.window,
            status="pending",
        )

    async def unschedule_substitution(self, match_id, club_id) -> None:
        live = live_matches.get(match_id)
        if live is None:
            raise HTTPException(status_code=404, detail="El partido no está en juego")

        team_id = str(club_id)
        try:
            get_side(team_id, live.info)
        except ClubNotInMatch as e:
            raise HTTPException(
                status_code=403, detail="El club no juega este partido"
            ) from e

        _coach_in_match(live, team_id)

        try:
            cancel(live.pending_substitutions, team_id)
        except NoPendingSubstitution as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

    async def set_penalty_order(
        self,
        match_id: uuid.UUID,
        penalty_order_input: PenaltyOrderInput,
        club_id: uuid.UUID,
    ) -> None:
        live = live_matches.get(match_id)
        if live is None:
            raise HTTPException(status_code=404, detail="El partido no está en juego")

        team_id = str(club_id)
        try:
            get_side(team_id, live.info)
        except ClubNotInMatch as e:
            raise HTTPException(
                status_code=403, detail="El club no juega este partido"
            ) from e

        _coach_in_match(live, team_id)

        # la ventana está abierta desde penaltyShootoutStart hasta que arranca la tanda
        if live.phase != Phase.PENALTIES or live.shootout is not None:
            raise HTTPException(
                status_code=409, detail="No hay una ventana de penales abierta"
            )

        try:
            kickers = build_penalty_order(
                live.info,
                team_id,
                [str(k.player_id) for k in penalty_order_input.kickers],
            )
        except InvalidPenaltyOrder as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        behaviors = BehaviorRepository(self._session)
        codes = []
        for kicker in penalty_order_input.kickers:
            behavior = await behaviors.get_id_and_club(kicker.behavior_id, club_id)
            if behavior is None or behavior.kind != "player":
                raise HTTPException(
                    status_code=400, detail="El comportamiento no existe"
                )
            codes.append(behavior.code)

        load_penalty_order(live, team_id, kickers, codes)
