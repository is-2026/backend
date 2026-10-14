import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB


@dataclass
class SquadPlayerData:
    player_id: uuid.UUID
    is_starter: bool
    behavior_id: uuid.UUID | None = None


class LeagueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
