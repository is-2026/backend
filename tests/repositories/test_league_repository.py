import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.league import LeagueDB, LeagueEnrollmentDB, LeagueEnrollmentPlayerDB
from app.db.player import PlayerDB
from app.db.user import UserDB
from app.repositories.league_repository import LeagueRepository, SquadPlayerData


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
            id=uuid.uuid4(), name=f"Jugador {i}", number=i + 1,
            power=100, agility=100, control=30, speed=30, strength=40,
            club_id=club_id,
        )
        for i in range(6)
    ]
    behaviors = [
        BehaviorDB(
            id=uuid.uuid4(), name=f"Comp {i}",
            code="def decide_action(): pass", club_id=club_id,
        )
        for i in range(3)
    ]
    session.add_all(players + behaviors)
    await session.commit()
    return [
        SquadPlayerData(p.id, i < 3, behaviors[i].id if i < 3 else None)
        for i, p in enumerate(players)
    ]


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
    squad[5].behavior_id = squad[0].behavior_id  # le ponemos comportamiento a un suplente

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