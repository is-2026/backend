import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.match import MatchDB, MatchStatus
from app.db.standings import LeagueStandingsDB
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.db.player import PlayerDB
from app.db.user import UserDB
from app.repositories.league_repository import (
    LeagueRepository,
    SquadPlayerData,
    ClubAlreadyEnrolled,
    ClubNotEnrolled,
)


async def count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def make_club(session) -> uuid.UUID:
    user_id = uuid.uuid4()
    random_email = f"liga_{str(user_id)[:8]}@test.com"  # generamos un email unico a partir de la id
    session.add(UserDB(id=user_id, email=random_email, hashed_password="hash"))
    await session.flush()  # el usuario se inserta antes que el club
    club_id = uuid.uuid4()
    session.add(
        ClubDB(
            id=club_id,
            club_name="Club Liga",
            avatar_url="https://img.com/avatar.png",
            user_id=user_id,
        )
    )
    await session.commit()
    return club_id


async def make_named_club(session, name: str) -> uuid.UUID:
    user_id = uuid.uuid4()
    session.add(
        UserDB(id=user_id, email=f"{user_id}@test.com", hashed_password="hash")
    )
    await session.flush()
    club_id = uuid.uuid4()
    session.add(
        ClubDB(
            id=club_id,
            club_name=name,
            avatar_url="https://img.com/avatar.png",
            user_id=user_id,
        )
    )
    await session.commit()
    return club_id


async def make_squad(session, club_id) -> list[SquadPlayerData]:
    """6 jugadores y 3 comportamientos reales. Los 3 primeros son titulares."""
    players = [
        PlayerDB(
            id=uuid.uuid4(),
            name=f"Jugador {i}",
            number=i + 1,
            power=100,
            agility=100,
            control=30,
            speed=30,
            strength=40,
            club_id=club_id,
        )
        for i in range(6)
    ]
    behaviors = [
        BehaviorDB(
            id=uuid.uuid4(),
            name=f"Comp {i}",
            code="def decide_action(): pass",
            club_id=club_id,
        )
        for i in range(3)
    ]
    session.add_all(players + behaviors)
    await session.commit()
    return [
        SquadPlayerData(p.id, i < 3, behaviors[i].id if i < 3 else None)
        for i, p in enumerate(players)
    ]


async def create_liga(session, club_id, status):
    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name="LPF Chiqui mafia",
            hashed_password=None,
            max_clubs=5,
            match_duration_minutes=10,
            status=status,
            creator_club_id=club_id,
        )
    )
    await session.commit()
    return league_id


async def create(session, club_id, squad, password=None):
    return await LeagueRepository(session).create_with_enrollment(
        name="Liga",
        hashed_password=password,
        max_clubs=5,
        match_duration_minutes=10,
        club_id=club_id,
        squadPlayer=squad,
    )


async def test_create_with_enrollment_ok(session, session_factory):
    club_id = await make_club(session)
    squad = await make_squad(session, club_id)

    league = await create(session, club_id, squad)

    async with session_factory() as other:  # sesión aparte: se guardó de verdad
        stored = await other.get(LeagueDB, league.id)
        enrollments = await count(other, LeagueEnrollmentDB)
        rows = (await other.scalars(select(LeagueEnrollmentPlayerDB))).all()

    assert stored is not None
    assert stored.name == "Liga"
    assert stored.status == "not_started"
    assert stored.creator_club_id == club_id
    assert stored.hashed_password is None
    assert enrollments == 1  # el creador queda inscripto
    assert len(rows) == 6
    assert sum(r.is_starter for r in rows) == 3
    assert all(r.behavior_id is not None for r in rows if r.is_starter)
    assert all(r.behavior_id is None for r in rows if not r.is_starter)


async def test_create_with_enrollment_saves_hashed_password(session, session_factory):
    club_id = await make_club(session)
    squad = await make_squad(session, club_id)

    league = await create(session, club_id, squad, password="hash")

    async with session_factory() as other:
        stored = await other.get(LeagueDB, league.id)
    assert stored.hashed_password == "hash"


async def test_substitute_behavior_is_not_saved(session):
    club_id = await make_club(session)
    squad = await make_squad(session, club_id)
    squad[5].behavior_id = squad[
        0
    ].behavior_id  # le ponemos comportamiento a un suplente

    await create(session, club_id, squad)

    rows = (
        await session.scalars(
            select(LeagueEnrollmentPlayerDB).where(
                LeagueEnrollmentPlayerDB.is_starter.is_(False)
            )
        )
    ).all()
    assert len(rows) == 3
    assert all(r.behavior_id is None for r in rows)


async def test_duplicate_player_raises_and_saves_nothing(session):
    club_id = await make_club(session)
    squad = await make_squad(session, club_id)
    squad.append(SquadPlayerData(squad[0].player_id, False, None))  # repetido

    with pytest.raises(IntegrityError):
        await create(session, club_id, squad)

    assert await count(session, LeagueDB) == 0
    assert await count(session, LeagueEnrollmentDB) == 0


async def test_get_league_ret_league(session):
    club_id = await make_club(session)
    league_id = await create_liga(session, club_id=club_id, status="not_started")

    league = await LeagueRepository(session).get(league_id)

    assert league is not None
    assert league.id == league.id
    assert league.name == "LPF Chiqui mafia"


async def test_get_league_id_not_exist(session):
    league = await LeagueRepository(session).get(uuid.uuid4())

    assert league is None


async def add_league(session, club_id, name, status, password=None):
    league_id = uuid.uuid4()
    session.add(
        LeagueDB(
            id=league_id,
            name=name,
            hashed_password=password,
            max_clubs=5,
            match_duration_minutes=10,
            status=status,
            creator_club_id=club_id,
        )
    )
    await session.commit()
    return league_id


async def test_list_not_started_empty(session):
    result = await LeagueRepository(session).list_not_started()

    assert result == []


async def test_list_not_started_only_returns_not_started(session):
    club_id = await make_club(session)
    await add_league(session, club_id, "publica", "not_started")
    await add_league(session, club_id, "privada", "not_started", password="hash")
    await add_league(session, club_id, "iniciada", "started")
    await add_league(session, club_id, "terminada", "finished")

    result = await LeagueRepository(session).list_not_started()

    assert len(result) == 2
    names = [league.name for league in result]
    assert "publica" in names
    assert "privada" in names
    assert "iniciada" not in names
    assert "terminada" not in names


async def test_list_clubs_of_league(session):
    club_id = await make_club(session)
    league_id = await add_league(session, club_id, "liga", "not_started")
    session.add(
        LeagueEnrollmentDB(id=uuid.uuid4(), league_id=league_id, club_id=club_id)
    )
    await session.commit()

    clubs = await LeagueRepository(session).list_clubs_of_league(league_id)

    assert len(clubs) == 1
    assert clubs[0].id == club_id
    assert clubs[0].club_name == "Club Liga"


async def test_list_clubs_of_league_without_enrollments(session):
    club_id = await make_club(session)
    league_id = await add_league(session, club_id, "liga", "not_started")

    clubs = await LeagueRepository(session).list_clubs_of_league(league_id)

    assert clubs == []


async def test_add_enrollment(session):
    # creamos club, liga y equipo
    club_id = await make_club(session)
    league_id = await add_league(session, club_id, "liga", "not_started")
    squad = await make_squad(session, club_id)

    repo = LeagueRepository(session)

    # inscribimos al club con el equipo generado
    await repo.add_enrollment(league_id, club_id, squad)

    # verificamos que efectivamente se inscribio
    clubs = await repo.list_clubs_of_league(league_id)
    assert len(clubs) == 1
    assert clubs[0].id == club_id


async def test_add_enrollment_already_enrolled(session):
    # creamos club, liga y equipo
    club_id = await make_club(session)
    league_id = await add_league(session, club_id, "Liga 2", "not_started")
    squad = await make_squad(session, club_id)

    repo = LeagueRepository(session)

    # inscribimos
    await repo.add_enrollment(league_id, club_id, squad)

    # volvemos a inscribir y verificamos la excepcion (el club ya esta inscripto en esta liga)
    with pytest.raises(ClubAlreadyEnrolled):
        await repo.add_enrollment(league_id, club_id, squad)


async def test_remove_enrollment_success(session):
    # creamos la liga, el club y el equipo
    club_id = await make_club(session)
    league_id = await add_league(session, club_id, "Liga para borrar", "not_started")
    squad = await make_squad(session, club_id)

    repo = LeagueRepository(session)

    # lo inscribimos
    await repo.add_enrollment(league_id, club_id, squad)

    # verificamos que se inscribio
    clubs_antes = await repo.list_clubs_of_league(league_id)
    assert len(clubs_antes) == 1

    # ejecutamos el metodo (borrar inscripcion)
    await repo.remove_enrollment(league_id, club_id)

    # comprobamos que ya no este inscripto
    clubs_despues = await repo.list_clubs_of_league(league_id)
    assert len(clubs_despues) == 0

    # tambien verificamos que los jugadores se hayan borrado (esto es la cascada manual que implementamos en el metodo)
    jugadores_restantes = (
        await session.scalars(select(LeagueEnrollmentPlayerDB))
    ).all()
    assert len(jugadores_restantes) == 0


async def test_remove_enrollment_not_enrolled(session):
    # creamos la liga y el club, pero no lo inscribimos
    club_id = await make_club(session)
    league_id = await add_league(session, club_id, "Liga", "not_started")

    repo = LeagueRepository(session)

    # ejecutamos el metodo (borrar inscripcion) y esperamos la excepcion ClubNotEnrolled
    with pytest.raises(ClubNotEnrolled):
        await repo.remove_enrollment(league_id, club_id)


async def test_start_league_success(session, session_factory):
    # creamos el club creador y la liga, y lo inscribimos
    creator_club_id = await make_club(session)
    league_id = await add_league(
        session, creator_club_id, "Liga Test Start", "not_started"
    )
    repo = LeagueRepository(session)
    squad_creator = await make_squad(session, creator_club_id)
    await repo.add_enrollment(league_id, creator_club_id, squad_creator)

    # creamos e inscribimos 3 clubes mas (N=4 total, par)
    club_ids = [creator_club_id]
    for _ in range(3):
        other_club_id = await make_club(session)
        squad_other = await make_squad(session, other_club_id)
        await repo.add_enrollment(league_id, other_club_id, squad_other)
        club_ids.append(other_club_id)

    # INICIAMOS LA LIGA
    await repo.start_league(league_id)

    # verificamos en una sesion limpia que los datos estan persistidos
    async with session_factory() as other:
        # verificamos el estado de la liga
        stored_league = await other.get(LeagueDB, league_id)
        assert stored_league is not None
        assert stored_league.status == "started"

        # verificamos la tabla de posiciones (standings)
        standings_result = await other.execute(
            select(LeagueStandingsDB).where(LeagueStandingsDB.league_id == league_id)
        )
        standings = standings_result.scalars().all()

        assert len(standings) == 4  # una fila por club inscripto

        # comprobamos la inicializacion en cero y que los ranks sean del 1 al 4
        rangos_usados = set()
        for s in standings:
            assert s.club_id in club_ids
            assert s.points == 0
            assert s.matches_played == 0
            assert s.won == 0
            assert s.drawn == 0
            assert s.lost == 0
            assert s.goals_for == 0
            assert s.goals_against == 0
            rangos_usados.add(s.rank)

        assert rangos_usados == {1, 2, 3, 4}  # Los rangos deben ser únicos secuenciales

        # verificamos el fixture (los partidos generados)
        matches_result = await other.execute(
            select(MatchDB).where(MatchDB.league_id == league_id)
        )
        matches = matches_result.scalars().all()

        # N=4 equipos
        # Fechas = 3. Partidos totales = (4*3)/2 = 6
        assert len(matches) == 6

        for m in matches:
            assert m.status == MatchStatus.scheduled
            assert m.home_score is None
            assert m.away_score is None
            assert m.home_club_id != m.away_club_id  # nadie juega contra si mismo
            assert m.round_number in [1, 2, 3]  # todos los partidos deben tener un round_number valido

        # verificamos integridad de las fechas
        # en N=4, cada fecha debe tener exactamente 2 partidos
        partidos_por_fecha = {1: 0, 2: 0, 3: 0}
        for m in matches:
            partidos_por_fecha[m.round_number] += 1

        assert partidos_por_fecha[1] == 2
        assert partidos_por_fecha[2] == 2
        assert partidos_por_fecha[3] == 2

#Tests para el ranking

# anota a un club en la tabla de una liga, con su puesto y sus puntos
# dos clubes de la misma liga no pueden tener el mismo puesto
async def add_standing(session, league_id, club_id, rank, **stats):
    session.add(
        LeagueStandingsDB(league_id=league_id, club_id=club_id, rank=rank, **stats)
    )
    await session.commit()


# creamos un club que juega en dos ligas publicas y sumamos los puntos obtenidos en las dos
async def test_list_ranking_totals_sums_public_leagues(session):
    club = await make_club(session)
    liga1 = await add_league(session, club, "Liga 1", "started")
    liga2 = await add_league(session, club, "Liga 2", "finished")
    await add_standing(session, liga1, club, 1, points=6, matches_played=2, won=2,
                       goals_for=5, goals_against=1)
    await add_standing(session, liga2, club, 1, points=3, matches_played=3, won=1,
                       lost=2, goals_for=4, goals_against=6)

    result = await LeagueRepository(session).list_ranking_totals()

    assert len(result) == 1
    assert result[0].points == 9  # 6 + 3
    assert result[0].matches_played == 5  # 2 + 3
    assert result[0].goals_for == 9  # 5 + 4
    assert result[0].goals_against == 7  # 1 + 6


# creamos una liga privada, no deberia contar
async def test_list_ranking_totals_ignores_private_leagues(session):
    club = await make_club(session)
    liga = await add_league(session, club, "Privada", "started", password="hash")
    await add_standing(session, liga, club, 1, points=9, matches_played=3)

    assert await LeagueRepository(session).list_ranking_totals() == []


# creamos una liga que no arranco, no deberia contar
async def test_list_ranking_totals_ignores_not_started_leagues(session):
    club = await make_club(session)
    liga = await add_league(session, club, "Liga", "not_started")
    await add_standing(session, liga, club, 1, points=3, matches_played=1)

    assert await LeagueRepository(session).list_ranking_totals() == []


# creamos dos clubes en la liga pero uno no jugo, ese no aparece
async def test_list_ranking_totals_excludes_clubs_without_matches(session):
    con_partidos = await make_club(session)
    sin_partidos = await make_club(session)
    liga = await add_league(session, con_partidos, "Liga", "started")
    await add_standing(session, liga, con_partidos, 1, points=3, matches_played=1)
    await add_standing(session, liga, sin_partidos, 2)

    result = await LeagueRepository(session).list_ranking_totals()

    assert [t.club_id for t in result] == [con_partidos]

async def test_get_squad_by_match_returns_enrolled_players_ordered(session):
    home = await make_named_club(session, "Local")
    away = await make_named_club(session, "Visita")
    other = await make_named_club(session, "Tercero")

    league_id = await add_league(session, home, "Liga", "started")
    repo = LeagueRepository(session)
    home_squad = await make_squad(session, home)
    away_squad = await make_squad(session, away)
    other_squad = await make_squad(session, other)
    # invertimos titulares y suplentes de home: titulares pasan a ser camisetas 4, 5, 6
    b_id = home_squad[0].behavior_id
    home_squad_custom = [
        SquadPlayerData(sp.player_id, i >= 3, b_id if i >= 3 else None)
        for i, sp in enumerate(home_squad)
    ]

    await repo.add_enrollment(league_id, home, home_squad_custom)
    await repo.add_enrollment(league_id, away, away_squad)
    await repo.add_enrollment(league_id, other, other_squad)

    match_id = uuid.uuid4()
    session.add(
        MatchDB(
            id=match_id,
            home_club_id=home,
            away_club_id=away,
            league_id=league_id,
            round_number=1,
        )
    )
    await session.commit()

    squad = await repo.get_squad_by_match(match_id)

    assert len(squad) == 12
    home_members = [m for m in squad if m.club_id == home]
    assert [m.player.number for m in home_members] == [4, 5, 6, 1, 2, 3]
    assert [m.is_starter for m in home_members] == [True] * 3 + [False] * 3
    assert all(m.behavior is not None for m in home_members[:3])
    assert all(m.behavior is None for m in home_members[3:])


async def test_update_standings_and_finish_league(session, session_factory):
    # A, B, C en orden alfabetico inicial (ranks 1, 2, 3)
    club_a = await make_named_club(session, "Arsenal")
    club_b = await make_named_club(session, "Boca")
    club_c = await make_named_club(session, "Chacarita")

    league_id = await add_league(session, club_a, "Liga", "not_started")
    repo = LeagueRepository(session)
    for c in (club_a, club_b, club_c):
        await repo.add_enrollment(league_id, c, await make_squad(session, club_c if False else c))

    await repo.start_league(league_id)

    # Fecha 1: Chacarita (3) le gana 2-0 a Arsenal (1) -> intercambian ranks sin violar restriccion
    await repo.update_standings(league_id, club_c, club_a, home_score=2, away_score=0)

    # Fecha 2: Boca empata 1-1 con Arsenal
    await repo.update_standings(league_id, club_b, club_a, home_score=1, away_score=1)

    await repo.finish_league(league_id)

    async with session_factory() as other:
        league = await other.get(LeagueDB, league_id)
        assert league.status == "finished"

        rows = (
            await other.scalars(
                select(LeagueStandingsDB)
                .where(LeagueStandingsDB.league_id == league_id)
                .order_by(LeagueStandingsDB.rank)
            )
        ).all()

    # chequeo el estado final de la tabla:
    # 1° Chacarita (3 pts, +2), 2° Boca (1 pt, 0), 3° Arsenal (1 pt, -2)
    assert [r.club_id for r in rows] == [club_c, club_b, club_a]
    assert [r.rank for r in rows] == [1, 2, 3]

    chaca, boca, arsenal = rows
    assert (chaca.points, chaca.matches_played, chaca.won, chaca.drawn, chaca.lost, chaca.goals_for, chaca.goals_against, chaca.goals_dif) == (3, 1, 1, 0, 0, 2, 0, 2)
    assert (boca.points, boca.matches_played, boca.won, boca.drawn, boca.lost, boca.goals_for, boca.goals_against, boca.goals_dif) == (1, 1, 0, 1, 0, 1, 1, 0)
    assert (arsenal.points, arsenal.matches_played, arsenal.won, arsenal.drawn, arsenal.lost, arsenal.goals_for, arsenal.goals_against, arsenal.goals_dif) == (1, 2, 0, 1, 1, 1, 3, -2)
