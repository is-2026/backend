import uuid

from fastapi import HTTPException, status
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.club_api_base import BaseClubApi
from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.models.club import Club
from app.models.change_coach_input import ChangeCoachInput
from app.models.create_club_input import CreateClubInput
from app.repositories.club_repository import ClubAlreadyExists, ClubRepository
from app.repositories.behavior_repository import BehaviorRepository
from app.impl.ranking_api_impl import sort_standings
from app.models.club_profile import ClubProfile
from app.repositories.league_repository import ClubRankingTotals, LeagueRepository

CLUB_NAME_MAX_LENGTH = 50
AVATAR_URL_MAX_LENGTH = 512

_url_adapter = TypeAdapter(HttpUrl)


def _validate_club_name(raw_club_name: str) -> str:
    club_name = raw_club_name.strip()
    if not 1 <= len(club_name) <= CLUB_NAME_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El nombre del club debe tener entre 1 y {CLUB_NAME_MAX_LENGTH} caracteres",
        )
    return club_name


def _validate_avatar_url(raw_url: str) -> str:
    url = raw_url.strip()
    if len(url) > AVATAR_URL_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL de avatar demasiado larga",
        )
    try:
        _url_adapter.validate_python(url)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="URL de avatar inválida"
        ) from e
    return url


class ClubApiImpl(BaseClubApi):
    def __init__(self, session: AsyncSession, user_id: uuid.UUID | None = None) -> None:
        self._session = session
        self._user_id = user_id

    async def create_club(self, create_club_input: CreateClubInput) -> Club:
        if self._user_id is None:
            raise RuntimeError("create_club requiere user_id")  # lanzo una excepcion
        club_name = _validate_club_name(create_club_input.club_name)
        avatar_url = _validate_avatar_url(create_club_input.avatar_url)
        try:
            club = await ClubRepository(self._session).create(
                self._user_id, club_name, avatar_url, DEFAULT_BEHAVIORS
            )
        except ClubAlreadyExists as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El usuario ya tiene un club",
            ) from e
        return Club(
            id=club.id,
            club_name=club.club_name,
            avatar_url=club.avatar_url,
            user_id=club.user_id,
            created_at=club.created_at,
        )

    async def change_coach(
        self, change_coach_input: ChangeCoachInput, club_id: uuid.UUID
    ) -> Club:
        behavior_id = change_coach_input.behavior_id

        if behavior_id is not None:
            behavior = await BehaviorRepository(self._session).get_id_and_club(
                behavior_id, club_id
            )
            if behavior is None:
                raise HTTPException(
                    status_code=400, detail="El comportamiento no existe"
                )
            if behavior.kind != "coach":
                raise HTTPException(
                    status_code=400, detail="El comportamiento es de jugador"
                )

        club = await ClubRepository(self._session).update_coach(club_id, behavior_id)
        if club is None:
            raise HTTPException(status_code=404, detail="El club no existe")

        return Club(
            id=club.id,
            club_name=club.club_name,
            avatar_url=club.avatar_url,
            user_id=club.user_id,
            created_at=club.created_at,
            coach_behavior_id=club.coach_behavior_id,
        )
    
    async def get_my_club(self, club_id: uuid.UUID) -> Club:
        club = await ClubRepository(self._session).get_by_id(club_id)
        if club is None:
            raise HTTPException(status_code=404, detail="El club no existe")
        return Club(
            id=club.id,
            club_name=club.club_name,
            avatar_url=club.avatar_url,
            user_id=club.user_id,
            created_at=club.created_at,
            coach_behavior_id=club.coach_behavior_id,
        )

    async def get_club(self, club_id: uuid.UUID) -> ClubProfile:
        club = await ClubRepository(self._session).get_by_id(club_id)
        if club is None:
            raise HTTPException(status_code=404, detail="El club no existe")

        # traer informacion del GET /ranking y buscamos la fila del club
        totals = await LeagueRepository(self._session).list_ranking_totals()
        ordered = sort_standings(totals)

        # el club aun no participo en ligas publicas
        stats = ClubRankingTotals(
            club_id=club.id, club_name=club.club_name, avatar_url=club.avatar_url,
            points=0, matches_played=0, won=0, won_penalties=0, drawn=0,
            lost=0, goals_for=0, goals_against=0,
        )
        ranking_position = None
        for position, row in enumerate(ordered, start=1):
            if row.club_id == club.id:
                ranking_position = position
                stats = row
                break

        return ClubProfile(
            id=club.id,
            club_name=club.club_name,
            avatar_url=club.avatar_url,
            created_at=club.created_at,
            ranking_position=ranking_position,
            points=stats.points,
            matches_played=stats.matches_played,
            won=stats.won,
            won_penalties=stats.won_penalties,
            drawn=stats.drawn,
            lost=stats.lost,
            goals_for=stats.goals_for,
            goals_against=stats.goals_against,
        )
