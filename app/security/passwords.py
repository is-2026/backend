import asyncio

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def _hash_sync(plain: str) -> str:
    return _password_hash.hash(plain)


def _verify_sync(plain: str, hashed: str) -> bool:
    return _password_hash.verify(plain, hashed)


async def hash_password(plain: str) -> str:
    return await asyncio.to_thread(_hash_sync, plain)


async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_sync, plain, hashed)