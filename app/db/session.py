import logging
import os
from collections.abc import AsyncIterator

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}.")
    return value


def build_database_url() -> URL:
    return URL.create(
        drivername="mysql+aiomysql",
        username=_require("MYSQL_USER"),
        password=_require("MYSQL_PASSWORD"),
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=_require("MYSQL_DATABASE"),
        query={"charset": "utf8mb4"},
    )


engine = create_async_engine(build_database_url(), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por request, cerrada al terminar."""
    async with SessionLocal() as session:
        yield session


async def check_connection() -> None:
    """Ejecuta un SELECT 1; lanza excepción si no puede conectarse a MySQL."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.warning("Conexión a MySQL OK")
