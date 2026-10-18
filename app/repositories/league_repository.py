import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB


class ClubAlreadyEnrolled(Exception):
    """El club ya está inscripto en esta liga"""

class ClubNotEnrolled(Exception):
    """El club no está inscripto en esta liga"""

@dataclass
class SquadPlayerData:
    player_id: uuid.UUID
    is_starter: bool
    behavior_id: uuid.UUID | None = None


class LeagueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # crea la liga junto con su dueño
    async def create_with_enrollment(
        self,
        name: str,
        hashed_password: str | None,
        max_clubs: int,
        match_duration_minutes: int,
        club_id: uuid.UUID,
        squadPlayer: list[SquadPlayerData],
    ) -> LeagueDB:
        league = LeagueDB(
            id=uuid.uuid4(),
            name=name,
            hashed_password=hashed_password,
            max_clubs=max_clubs,
            match_duration_minutes=match_duration_minutes,
            status="not_started",
            creator_club_id=club_id,
        )
        enrollment = LeagueEnrollmentDB(
            id=uuid.uuid4(), league_id=league.id, club_id=club_id
        )
        enrolled_players = [
            LeagueEnrollmentPlayerDB(
                id=uuid.uuid4(),
                enrollment_id=enrollment.id,
                player_id=sp.player_id,
                is_starter=sp.is_starter,
                behavior_id=sp.behavior_id if sp.is_starter else None,
            )
            for sp in squadPlayer
        ]

        try:
            self._session.add(league)
            await self._session.flush()  # por las FK
            self._session.add(enrollment)
            await self._session.flush()
            self._session.add_all(enrolled_players)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise

        return league

    # inscripcion a una liga
    async def add_enrollment(
        self,
        league_id: uuid.UUID,
        club_id: uuid.UUID,
        squadPlayer: list[SquadPlayerData],
    ) -> None:
        # creo la tabla de inscripcion
        enrollment = LeagueEnrollmentDB(
            id=uuid.uuid4(), league_id=league_id, club_id=club_id
        )
        # mapeo cada squadPlayer a LeagueEnrollmentPlayerDB con el enrollment que creamos antes
        enrolled_players = [
            LeagueEnrollmentPlayerDB(
                id=uuid.uuid4(),
                enrollment_id=enrollment.id,
                player_id=sp.player_id,
                is_starter=sp.is_starter,
                behavior_id=sp.behavior_id
                if sp.is_starter
                else None,  # si no es titular-> behavior=None
            )
            for sp in squadPlayer
        ]
        try:
            self._session.add(enrollment)
            await self._session.flush()
            self._session.add_all(enrolled_players)
            await self._session.commit()
        except IntegrityError as e:
            await self._session.rollback()
            raise ClubAlreadyEnrolled(club_id) from e

    async def list_not_started(self) -> list[LeagueDB]:
        result = await self._session.execute(
            select(LeagueDB).where(LeagueDB.status == "not_started")
        )
        return list(result.scalars().all())

    async def list_clubs_of_league(self, league_id: uuid.UUID) -> list[ClubDB]:
        # primero las inscripciones de la liga, después busco el club de cada una
        result = await self._session.execute(
            select(LeagueEnrollmentDB).where(LeagueEnrollmentDB.league_id == league_id)
        )
        clubs = []
        for enrollment in result.scalars().all():
            club = await self._session.get(ClubDB, enrollment.club_id)
            clubs.append(club)
        return clubs

    async def get(
        self, league_id: uuid.UUID
    ) -> LeagueDB | None:  # Si no encuetro la liga devuelvo None
        return await self._session.get(
            LeagueDB, league_id
        )  # busco una fila por el id de la liga usando _session.get

    async def remove_enrollment(self, league_id: uuid.UUID, club_id: uuid.UUID) -> None:
        # buscamos la inscripcion
        result = await self._session.execute(
            select(LeagueEnrollmentDB)
            .where(
                LeagueEnrollmentDB.league_id == league_id,
                LeagueEnrollmentDB.club_id == club_id
            )
        )
        enrollment = result.scalars().first()

        # si no existe lanzamos la excepcion
        if not enrollment:
            raise ClubNotEnrolled()

        # borramos primero los jugadores asociados a esta inscripcion (por la FK)
        await self._session.execute(
            delete(LeagueEnrollmentPlayerDB)
            .where(
                LeagueEnrollmentPlayerDB.enrollment_id == enrollment.id
            )
        )
        # borramos la inscripcion y confirmamos
        await self._session.delete(enrollment)
        await self._session.commit()
