import pytest
import uuid

from sqlalchemy import select

from app.db.user import UserDB
from app.repositories.user_repository import EmailExists, UserRepository


async def test_create_persists_the_user(session, session_factory):
    user = await UserRepository(session).create("ana@test.com", "hash")

    async with session_factory() as other:
        stored = await other.get(UserDB, user.id)
    assert stored is not None
    assert stored.email == "ana@test.com"
    assert stored.hashed_password == "hash"


async def test_create_with_existing_email_raises_email_exists(session):
    repo = UserRepository(session)
    await repo.create("ana@test.com", "hash")

    with pytest.raises(EmailExists):
        await repo.create("ana@test.com", "otro-hash")


async def test_session_is_still_usable_after_email_exists(session):
    repo = UserRepository(session)
    await repo.create("ana@test.com", "hash")
    with pytest.raises(EmailExists):
        await repo.create("ana@test.com", "otro-hash")

    await repo.create("beto@test.com", "hash")

    emails = (await session.scalars(select(UserDB.email))).all()
    assert sorted(emails) == ["ana@test.com", "beto@test.com"]


async def test_get_by_email_return_user(session):
    #creo usuario
    user_id = uuid.uuid4()
    user_db = UserDB(
        id=user_id,
        email="test@example.com",
        hashed_password="password123"
    )
    session.add(user_db)
    await session.commit()
    consult_repo = UserRepository(session)

    result = await consult_repo.get_by_email("test@example.com")
    assert result.id == user_id


async def test_get_by_email_return_none(session):
    consult_repo = UserRepository(session)

    # este email podria existir en la bd -> en ese caso fallaria
    result = await consult_repo.get_by_email("wrong@email.com")
    assert result is None