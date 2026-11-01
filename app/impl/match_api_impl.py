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
from app.repositories.behavior_repository import BehaviorRepository
from app.repositories.match_repository import MatchRepository
from app.ws.connection_manager import ConnectionManager
from app.ws.match.runner import LiveMatch, Phase, live_matches
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


class MatchApiImpl(BaseMatchApi):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_match(self, match_id: uuid.UUID) -> Match:
        # buscamos el partido en la db
        match_db = await MatchRepository(self._session).get_by_id(match_id)
        if not match_db:
            raise HTTPException(status_code=404, detail="El partido no existe")
        # mapeamos al modelo pydantic
        return Match(
            id=str(match_db.id),
            home_club_id=str(match_db.home_club_id),
            away_club_id=str(match_db.away_club_id),
            status=match_db.status.value,
            home_score=match_db.home_score,
            away_score=match_db.away_score,
        )

    async def set_lineup(self, match_id, submit_lineup_input) -> Match:
        raise NotImplementedError

    async def change_live_behavior(
        self, match_id, player_id, change_live_behavior_request
    ) -> None:
        raise NotImplementedError

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

        behavior = await BehaviorRepository(self._session).get_id_and_club(
            schedule_substitution_input.substitution_behavior_id, club_id
        )
        if behavior is None or behavior.kind != "player":
            raise HTTPException(status_code=400, detail="El comportamiento no existe")

        if match_id not in live_matches:
            # terminó mientras fuimos a buscar el behavior a la db
            raise HTTPException(status_code=404, detail="El partido no está en juego")

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

        try:
            cancel(live.pending, team_id)
        except NoPendingSubstitution as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
