import os

import pymysql
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import build_database_url, get_session
from app.db.user import UserDB
from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.main import app

TEST_DATABASE = "futbot_test"

# TODO: usar todo Base.metadata cuando exista ClubDB (players.club_id -> clubs.id)
TABLES = [UserDB.__table__, BehaviorDB.__table__, ClubDB.__table__]


@pytest.fixture(scope="session", autouse=True)
def crear_base_de_test():
    """Una vez por corrida: crea futbot_test (como root) y le da permisos al usuario."""
    url = build_database_url()
    conn = pymysql.connect(
        host=url.host,
        port=url.port,
        user="root",
        password=os.environ["MYSQL_ROOT_PASSWORD"],
    )
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DATABASE}")
        cur.execute(f"GRANT ALL ON {TEST_DATABASE}.* TO %s@'%%'", (url.username,))
    conn.close()


@pytest.fixture
async def session_factory():
    """Engine apuntando a futbot_test, con las tablas creadas y vaciadas al final."""
    url = build_database_url().set(database=TEST_DATABASE)
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=TABLES)

    yield async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        for table in reversed(TABLES):
            await conn.execute(table.delete())
    await engine.dispose()


@pytest.fixture
async def session(session_factory):
    """Sesión para preparar datos (Arrange) y verificar la base (Assert)."""
    async with session_factory() as s:
        yield s


@pytest.fixture
async def client(session_factory):
    """Cliente HTTP contra la app, con get_session redirigida a la base de test."""

    async def get_test_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = get_test_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
