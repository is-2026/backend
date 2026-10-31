import uuid
import pytest
from sqlalchemy import func, select

from app.behaviors.defaults import DefaultBehaviorData
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.user import UserDB
from app.repositories.club_repository import (
    ClubAlreadyExists,
    ClubRepository,
)
from app.db.behavior import BehaviorDB

CLUB_NAME = "Instituto"
AVATAR_URL = "https://img.com/avatar.png"


@pytest.fixture
def default_behaviors():
    """Devuelve una lista base de comportamientos válida para los tests."""
    return [
        DefaultBehaviorData(name="Atacar", code="atacaratacaratacar"),
        DefaultBehaviorData(name="Defender", code="defenderdefenderdefender"),
        DefaultBehaviorData(name="Quedarse quieto", code="quietoquietoquieto"),
    ]


@pytest.fixture
async def user(session):
    """Crea un usuario real en la base de datos de test y lo devuelve."""
    u = UserDB(email="hola@prueba.com", hashed_password="hash")
    session.add(u)
    await session.commit()
    return u


async def test_create_persists_the_club(
    session, session_factory, user, default_behaviors
):
    club = await ClubRepository(session).create(
        user.id, CLUB_NAME, AVATAR_URL, default_behaviors
    )

    async with session_factory() as other:
        stored = await other.get(ClubDB, club.id)
    assert stored is not None
    assert stored.club_name == CLUB_NAME
    assert stored.avatar_url == AVATAR_URL
    assert stored.user_id == user.id
    assert stored.created_at is not None


async def test_create_persists_the_default_behaviors(
    session, session_factory, user, default_behaviors
):
    club = await ClubRepository(session).create(
        user.id, CLUB_NAME, AVATAR_URL, default_behaviors
    )

    async with session_factory() as other:
        stored = (
            await other.scalars(select(BehaviorDB).where(BehaviorDB.club_id == club.id))
        ).all()
    assert sorted((b.name, b.code) for b in stored) == sorted(default_behaviors)


async def test_create_with_existing_club_raises_club_exists(
    session, session_factory, user, default_behaviors
):
    user_id = user.id  # el rollback del repositorio expira `user`
    repo = ClubRepository(session)
    await repo.create(user_id, CLUB_NAME, AVATAR_URL, default_behaviors)

    with pytest.raises(ClubAlreadyExists):
        await repo.create(user_id, "Otro club", AVATAR_URL, default_behaviors)

    async with session_factory() as other:
        clubs = await other.scalar(
            select(func.count()).select_from(ClubDB).where(ClubDB.user_id == user_id)
        )
        behaviors = await other.scalar(select(func.count()).select_from(BehaviorDB))
    assert clubs == 1
    assert behaviors == len(default_behaviors)

async def test_get_by_id(session, user, default_behaviors):
    club = await ClubRepository(session).create(
        user.id, CLUB_NAME, AVATAR_URL, default_behaviors
    )

    found = await ClubRepository(session).get_by_id(club.id)

    assert found.club_name == CLUB_NAME


async def test_get_by_id_unknown_returns_none(session):
    assert await ClubRepository(session).get_by_id(uuid.uuid4()) is None

async def test_update_coach_succes(session, user, default_behaviors):
    club = await ClubRepository(session).create(
        user.id, CLUB_NAME, AVATAR_URL, default_behaviors
    )

    behavior_id = uuid.uuid4()
    behavior_dt = BehaviorDB(
        id = behavior_id,
            name = "Gagardo",
            code = "def decide_coach():\n pass",
            club_id = club.id,
            kind= "coach"
    )
    session.add(behavior_dt)
    await session.commit()
    
    result = await ClubRepository(session).update_coach(club.id, behavior_dt.id)

    assert result is not None
    assert result.id == club.id 
    assert result.coach_behavior_id == behavior_dt.id

async def test_update_coach_club_id_invalid(session, user, default_behaviors):
    club = await ClubRepository(session).create(
        user.id, CLUB_NAME, AVATAR_URL, default_behaviors
    )

    behavior_id = uuid.uuid4()
    behavior_dt = BehaviorDB(
        id = behavior_id,
            name = "Gagardo",
            code = "def decide_coach():\n pass",
            club_id = club.id,
            kind= "coach"
    )
    session.add(behavior_dt)
    await session.commit()
    
    result = await ClubRepository(session).update_coach(uuid.uuid4(), behavior_dt.id)

    assert result is None

async def test_update_coach_not_behavior(session, user, default_behaviors):
    club = await ClubRepository(session).create(
        user.id, CLUB_NAME, AVATAR_URL, default_behaviors
    )
    await session.commit()
    
    result = await ClubRepository(session).update_coach(club.id, None)

    assert result is not None
    assert result.coach_behavior_id == None
