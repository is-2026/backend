import pytest
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
