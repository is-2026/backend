import uuid
import asyncio
import logging
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone

from app.apis.match_api_base import BaseMatchApi
from app.repositories.match_repository import MatchRepository
from app.db.match import MatchDB 
from app.models.match import Match
from app.models.substitution import Substitution
from sqlalchemy.ext.asyncio import AsyncSession
from app.ws.connection_manager import ConnectionManager

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
            away_score=match_db.away_score
        )

    async def set_lineup(self, match_id, submit_lineup_input) -> Match:
        raise NotImplementedError

    async def change_live_behavior(self, match_id, player_id, change_live_behavior_request) -> None:
        raise NotImplementedError

    async def schedule_substitution(self, match_id, schedule_substitution_input) -> Substitution:
        raise NotImplementedError

    async def unschedule_substitution(self, match_id) -> None:
        raise NotImplementedError