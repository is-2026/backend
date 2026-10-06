import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
from app.security.tokens import create_access_token
from app.ws.auth import authenticate
from app.ws.close_codes import UNAUTHORIZED
from tests.ws.conftest import FakeWebSocket


def _sign(payload: dict) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _in(minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


async def test_valid_token_returns_user_id_and_keeps_connection_open():
    ws = FakeWebSocket()
    user_id = uuid.uuid4()

    result = await authenticate(ws, create_access_token(user_id))

    assert result == user_id
    assert ws.closed_code is None


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "this-is-not-a-jwt",
        _sign({"sub": str(uuid.uuid4()), "exp": _in(-1)}),
        _sign({"sub": "abc", "exp": _in(5)}),
    ],
    ids=["sin_token", "vacio", "basura", "expirado", "sub_no_uuid"],
)
async def test_invalid_token_closes_with_4401(token):
    ws = FakeWebSocket()

    result = await authenticate(ws, token)

    assert result is None
    assert ws.closed_code == UNAUTHORIZED
