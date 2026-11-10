import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, delete, func, or_, select, update

from app.db.behavior import BehaviorDB
from app.db.match import MatchDB, MatchStatus
from app.db.player import PlayerDB
from app.db.standings import LeagueStandingsDB
from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.repositories.friendly_repository import SquadMember

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

@dataclass
class ClubRankingTotals:
    club_id: uuid.UUID
    club_name: str
    avatar_url: str
    points: int
    matches_played: int
    won: int
    won_penalties: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int


def _apply_score(
    row: LeagueStandingsDB,
    goals_for: int,
    goals_against: int,
    won_shootout: bool | None = None,
) -> None:
    """won_shootout: None si no hubo penales. Si hubo, si este club ganó la tanda.
    Los goles de la tanda no cuentan en goles a favor ni en contra."""
    row.matches_played += 1
    row.goals_for += goals_for
    row.goals_against += goals_against
    row.goals_dif = row.goals_for - row.goals_against
    if goals_for > goals_against:
        row.won += 1
        row.points += 3
    elif goals_for < goals_against:
        row.lost += 1
    elif won_shootout is None:
        row.drawn += 1
        row.points += 1
    elif won_shootout:
        row.won_penalties += 1
        row.points += 2
    else:
        row.lost += 1  # perder por penales da 0 puntos, como cualquier derrota


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
        allows_draws: bool = True,
        formation: str = "TRIANGLE",
    ) -> LeagueDB:
        league = LeagueDB(
            id=uuid.uuid4(),
            name=name,
            hashed_password=hashed_password,
            max_clubs=max_clubs,
            match_duration_minutes=match_duration_minutes,
            allows_draws=allows_draws,
            status="not_started",
            creator_club_id=club_id,
        )
        enrollment = LeagueEnrollmentDB(
            id=uuid.uuid4(), league_id=league.id, club_id=club_id, formation=formation
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
        formation: str = "TRIANGLE",
    ) -> None:
        # creo la tabla de inscripcion
        enrollment = LeagueEnrollmentDB(
            id=uuid.uuid4(), league_id=league_id, club_id=club_id, formation=formation
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
    
    async def list_leagues_of_club(self, club_id: uuid.UUID) -> list[LeagueDB]:
        # primero las inscripciones del club. después busco la liga de cada una
        result = await self._session.execute(
            select(LeagueEnrollmentDB).where(LeagueEnrollmentDB.club_id == club_id)
        )
        leagues = []
        for enrollment in result.scalars().all():
            league = await self._session.get(LeagueDB, enrollment.league_id)
            if league.status != "cancelled":
                leagues.append(league)
        return leagues
        
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

    async def get_enrollment(
        self, league_id: uuid.UUID, club_id: uuid.UUID
    ) -> LeagueEnrollmentDB | None:
        # busco la inscripcion del club en la liga (None si no esta inscripto)
        result = await self._session.execute(
            select(LeagueEnrollmentDB).where(
                LeagueEnrollmentDB.league_id == league_id,
                LeagueEnrollmentDB.club_id == club_id,
            )
        )
        return result.scalars().first()

    async def list_enrollment_players(
        self, enrollment_id: uuid.UUID
    ) -> list[LeagueEnrollmentPlayerDB]:
        # los 6 convocados de la inscripcion
        result = await self._session.execute(
            select(LeagueEnrollmentPlayerDB).where(
                LeagueEnrollmentPlayerDB.enrollment_id == enrollment_id
            )
        )
        return list(result.scalars().all())

    async def update_lineup(
        self,
        enrollment: LeagueEnrollmentDB,
        formation: str,
        squadPlayer: list[SquadPlayerData],
    ) -> None:
        enrollment.formation = formation

        # actualizo cada convocado con lo que mando el club
        players = await self.list_enrollment_players(enrollment.id)
        for player in players:
            for sp in squadPlayer:
                if sp.player_id == player.player_id:
                    player.is_starter = sp.is_starter
                    # si no es titular -> behavior=None
                    player.behavior_id = sp.behavior_id if sp.is_starter else None

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


    # suma por club las filas de la tabla de posiciones de las ligas publicas
    # en curso o terminadas. solo clubes con al menos un partido jugado
    async def list_ranking_totals(self) -> list[ClubRankingTotals]:
        result = await self._session.execute(
            select(
                ClubDB.id,
                ClubDB.club_name,
                ClubDB.avatar_url,
                func.sum(LeagueStandingsDB.points).label("points"),
                func.sum(LeagueStandingsDB.matches_played).label("matches_played"),
                func.sum(LeagueStandingsDB.won).label("won"),
                func.sum(LeagueStandingsDB.won_penalties).label("won_penalties"),
                func.sum(LeagueStandingsDB.drawn).label("drawn"),
                func.sum(LeagueStandingsDB.lost).label("lost"),
                func.sum(LeagueStandingsDB.goals_for).label("goals_for"),
                func.sum(LeagueStandingsDB.goals_against).label("goals_against"),
            )
            .join(LeagueDB, LeagueDB.id == LeagueStandingsDB.league_id)
            .join(ClubDB, ClubDB.id == LeagueStandingsDB.club_id)
            .where(
                LeagueDB.hashed_password.is_(None),  # pública
                LeagueDB.status.in_(["started", "finished"]),
            )
            .group_by(ClubDB.id, ClubDB.club_name, ClubDB.avatar_url)
            .having(func.sum(LeagueStandingsDB.matches_played) > 0)
        )
        # SUM devuelve Decimal en MySQL: casteo a int (RankingItem usa StrictInt)
        return [
            ClubRankingTotals(
                club_id=row.id,
                club_name=row.club_name,
                avatar_url=row.avatar_url,
                points=int(row.points),
                matches_played=int(row.matches_played),
                won=int(row.won),
                won_penalties=int(row.won_penalties),
                drawn=int(row.drawn),
                lost=int(row.lost),
                goals_for=int(row.goals_for),
                goals_against=int(row.goals_against),
            )
            for row in result.all()
        ]

    async def get_squad_by_match(self, match_id: uuid.UUID) -> list[SquadMember]:
        """Los convocados vigentes en la liga para los dos clubes de ese partido:
        primero los titulares, y dentro de cada grupo por numero de camiseta."""
        result = await self._session.execute(
            select(
                LeagueEnrollmentDB.club_id,
                PlayerDB,
                LeagueEnrollmentPlayerDB.is_starter,
                BehaviorDB,
            )
            .join(
                MatchDB,
                and_(
                    MatchDB.league_id == LeagueEnrollmentDB.league_id,
                    or_(
                        LeagueEnrollmentDB.club_id == MatchDB.home_club_id,
                        LeagueEnrollmentDB.club_id == MatchDB.away_club_id,
                    ),
                ),
            )
            .join(
                LeagueEnrollmentPlayerDB,
                LeagueEnrollmentPlayerDB.enrollment_id == LeagueEnrollmentDB.id,
            )
            .join(PlayerDB, PlayerDB.id == LeagueEnrollmentPlayerDB.player_id)
            .outerjoin(
                BehaviorDB, BehaviorDB.id == LeagueEnrollmentPlayerDB.behavior_id
            )
            .where(MatchDB.id == match_id)
            .order_by(LeagueEnrollmentPlayerDB.is_starter.desc(), PlayerDB.number)
        )
        return [SquadMember(*row) for row in result.all()]

    async def update_standings(
        self,
        league_id: uuid.UUID,
        home_club_id: uuid.UUID,
        away_club_id: uuid.UUID,
        home_score: int,
        away_score: int,
        penalty_winner_id: uuid.UUID | None = None,
    ) -> None:
        """penalty_winner_id: el club que ganó la tanda, None si no hubo penales."""
        result = await self._session.execute(
            select(LeagueStandingsDB, ClubDB.club_name)
            .join(ClubDB, ClubDB.id == LeagueStandingsDB.club_id)
            .where(LeagueStandingsDB.league_id == league_id)
            .order_by(LeagueStandingsDB.club_id)
            .with_for_update()  #bloqueo por fila para evitar race conditions (van a terminar muchos match a la vez)
            .execution_options(populate_existing=True)  #lee los datos actualizados despues del bloqueo
        )
        rows = result.all()

        for row, _ in rows:
            won_shootout = (
                None if penalty_winner_id is None else row.club_id == penalty_winner_id
            )
            if row.club_id == home_club_id:
                _apply_score(row, home_score, away_score, won_shootout)
            elif row.club_id == away_club_id:
                _apply_score(row, away_score, home_score, won_shootout)

        # paso intermedio con ranks negativos para no violar UniqueConstraint(league_id, rank)
        for idx, (row, _) in enumerate(rows, start=1):
            row.rank = -idx
        await self._session.flush()

        sorted_rows = sorted(
            rows,
            key=lambda item: (
                -item[0].points,
                -item[0].goals_dif,
                -item[0].goals_for,
                item[1].lower(),
            ),
        )
        for rank, (row, _) in enumerate(sorted_rows, start=1):
            row.rank = rank

        await self._session.commit()

    async def finish_league(self, league_id: uuid.UUID) -> None:
        await self._session.execute(
            update(LeagueDB)
            .where(LeagueDB.id == league_id)
            .values(status="finished")
        )
        await self._session.commit()

    async def get_standings(
        self, league_id: uuid.UUID
    ) -> list[tuple[LeagueStandingsDB, str]]:
        """Devuelve las filas de la tabla de posiciones junto con el nombre del club, y ya
        ordenadas por: Puntos (desc), Diferencia de gol (desc), Goles a favor (desc) y Nombre del club (asc)."""
        result = await self._session.execute(
            select(LeagueStandingsDB, ClubDB.club_name)
            .join(ClubDB, ClubDB.id == LeagueStandingsDB.club_id)
            .where(LeagueStandingsDB.league_id == league_id)
        )
        return sorted(
            result.all(),
            key=lambda item: (
                -item[0].points,
                -item[0].goals_dif,
                -item[0].goals_for,
                item[1].lower(),
            ),
        )
