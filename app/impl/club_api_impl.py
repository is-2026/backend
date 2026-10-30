import uuid

from fastapi import HTTPException, status
from pydantic import HttpUrl, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.club_api_base import BaseClubApi
from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.models.club import Club
from app.models.create_club_input import CreateClubInput
from app.repositories.club_repository import ClubAlreadyExists, ClubRepository

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
            raise RuntimeError("create_club requiere user_id") #lanzo una excepcion
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
