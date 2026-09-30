import pytest

from app.security.passwords import (
    hash_password,
    verify_password,
)


async def test_se_hashea_pass():
    hashed = await hash_password("secreto123")
    assert hashed != "secreto123"
    assert hashed.startswith("$argon2id$")


async def test_verify_acepta_la_password_correcta():
    hashed = await hash_password("secreto123")
    assert await verify_password("secreto123", hashed) is True


async def test_verify_rechaza_una_password_incorrecta():
    hashed = await hash_password("secreto123")
    assert await verify_password("otra-cosa", hashed) is False

