import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.match import MatchDB, MatchStatus
from app.db.standings import LeagueStandingsDB
from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB

from app.fixture.generator import generate_fixture


class ClubAlreadyEnrolled(Exception):
    """El club ya está inscripto en esta liga"""


class ClubNotEnrolled(Exception):
    """El club no está inscripto en esta liga"""

class LeagueStartFailure(Exception):
    """Fallo al inicializar la liga"""

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
            select(LeagueEnrollmentDB).where(
                LeagueEnrollmentDB.league_id == league_id,
                LeagueEnrollmentDB.club_id == club_id,
            )
        )
        enrollment = result.scalars().first()

        # si no existe lanzamos la excepcion
        if not enrollment:
            raise ClubNotEnrolled()

        # borramos primero los jugadores asociados a esta inscripcion (por la FK)
        await self._session.execute(
            delete(LeagueEnrollmentPlayerDB).where(
                LeagueEnrollmentPlayerDB.enrollment_id == enrollment.id
            )
        )
        # borramos la inscripcion y confirmamos
        await self._session.delete(enrollment)
        await self._session.commit()

    async def start_league(self, league_id: uuid.UUID) -> None:
        """
        Inicia la liga: cambia el estado, genera el fixture (partidos)
        y crea la tabla de posiciones en cero.
        Asume que las validaciones previas (cantidad de equipos, estado)
        ya se hicieron en la capa superior.
        """
        # obtenemos la liga y cambiamos su estado
        league = await self.get(league_id)
        if not league:
            raise ValueError(f"No se encontró la liga {league_id}")

        league.status = "started"

        # obtener los clubes inscriptos para generar fixture y tabla
        clubs = await self.list_clubs_of_league(league_id)
        club_ids = [club.id for club in clubs]  # esta va a ser la entrada del generador de fixture

        # generar la tabla de posiciones inicial (en cero)
        # como todos estan en cero, ordenamos por el ultimo criterio de desempate: orden alfabetico
        clubs_ordenados = sorted(clubs, key=lambda c: c.club_name.lower())

        standings_entries = []
        for rank, club in enumerate(clubs_ordenados, start=1):
            standings_entries.append(
                LeagueStandingsDB(
                    league_id=league_id,
                    club_id=club.id,
                    rank=rank,
                    # el resto (las estadisticas) inicializan en cero por defecto
                )
            )

        self._session.add_all(standings_entries)

        # generamos el fixture
        fechas = generate_fixture(club_ids)

        # persistir los partidos (MatchDB)
        match_entries = []

        # - MAPEO: iteramos sobre lo que nos devolvio el generador (list[list[tuple[UUID, UUID]]])
        #   y lo traducimos a instancias MatchDB
        # - enumerate nos sirve para saber que numero de fecha es (1, 2, 3...)
        for num_fecha, partidos_de_la_fecha in enumerate(fechas, start=1):
            for local_id, visitante_id in partidos_de_la_fecha:
                match_entries.append(
                    MatchDB(
                        id=uuid.uuid4(),
                        home_club_id=local_id,
                        away_club_id=visitante_id,
                        status=MatchStatus.scheduled,
                        league_id=league_id,
                        round_number=num_fecha,
                        home_score=None,
                        away_score=None,
                    )
                )
        self._session.add_all(match_entries)

        # commit final: todo se guarda en una sola transaccion atomica, evitano ligas a medio hacer
        # seria raro que falle en este nivel, pero lo manejamos aca
        try:
            await self._session.commit()
        except Exception as e:
            await self._session.rollback()
            raise LeagueStartFailure from e

        await self._session.commit()

    async def cancel_league(self, league_id: uuid.UUID) -> None:
        # cambiamos el estado de la liga a cancelada
        league = await self.get(league_id)
        league.status = "cancelled"
        await self._session.commit()

