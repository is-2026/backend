import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

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
    session.add(UserDB(id=user_id, email="liga@test.com", hashed_password="hash"))
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
