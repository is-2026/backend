import uuid

from fastapi import HTTPException, status

from app.apis.leagues_api_base import BaseLeaguesApi
from app.db.club import ClubDB
from app.db.session import SessionLocal
from app.models.create_league_input import CreateLeagueInput
from app.models.league_detail import LeagueDetail      
from app.repositories.league_repository import LeagueRepository, SquadPlayerData
from app.repositories.player_repository import PlayerRepository
from app.security.passwords import hash_password
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

MAX_CLUBS_LIMIT = 20
MIN_CLUBS = 3
SQUAD_SIZE = 6
STARTERS = 3

def _validate_league(data: CreateLeagueInput)->None:
    if not MIN_CLUBS <= data.max_clubs <= MAX_CLUBS_LIMIT:
        raise HTTPException(
            status_code=400,
            detail="max_clubs debe estar entre 3 y 20",
        )
    if len(data.players) != SQUAD_SIZE:
        raise HTTPException(400, "Se requieren exactamente 6 jugadores")

    starters = [p for p in data.players if p.is_starter]
    if len(starters) != STARTERS:
        raise HTTPException(400, "Se requieren exactamente 3 titulares")

    if len({p.player_id for p in data.players}) != SQUAD_SIZE:
        raise HTTPException(400, "Hay jugadores repetidos")

    if any(p.behavior_id is None for p in starters):
        raise HTTPException(400, "Cada titular debe tener un comportamiento asignado")

class LeaguesApiImpl(BaseLeaguesApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def create_league(self, 
                            create_league_input : CreateLeagueInput,
                            club_id : ClubDB) -> LeagueDetail:
        _validate_league(create_league_input)

        player_ids = [pl.player_id for pl in create_league_input.players]
        owned = await PlayerRepository(self._session).count_club_players(club_id.id, player_ids)
        if owned != SQUAD_SIZE:
            raise HTTPException(status_code=400, detail="Hay jugadores que no pertenecen a tu club")
        
        hashed = await hash_password(create_league_input.password) if create_league_input.password else None
        
        try:
            league = await LeagueRepository(self._session).create_with_enrollment(
                name=create_league_input.name,
                hashed_password=hashed,
                max_clubs=create_league_input.max_clubs,
                match_duration_minutes=create_league_input.match_duration_minutes,
                club_id=club_id.id,
                squadPlayer=[
                    SquadPlayerData(pl.player_id, pl.is_starter, pl.behavior_id)
                    for pl in create_league_input.players
                ]
            ) 
        except IntegrityError as exc_info:
            raise HTTPException(status_code=400, detail= "Datos de la liga invalidos") from exc_info

        return LeagueDetail(
            id= league.id,
            name=league.name,
            is_private=league.hashed_password is not None,
            max_clubs=league.max_clubs,
            status=league.status,
            registered_clubs=[{"club_id": club_id.id, "club_name": club_id.club_name}],
        )
