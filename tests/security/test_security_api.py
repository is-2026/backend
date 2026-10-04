import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import get_settings
from app.security.tokens import create_access_token
from app.security_api import get_token_bearerAuth


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_valid_token_returns_user_id_in_sub():
    user_id = uuid.uuid4()

    token = get_token_bearerAuth(_bearer(create_access_token(user_id)))

    assert token.sub == str(user_id)


def test_missing_token_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        get_token_bearerAuth(None)

    assert exc_info.value.status_code == 401


def test_malformed_token_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        get_token_bearerAuth(_bearer("this-is-not-a-jwt"))

    assert exc_info.value.status_code == 401


def test_token_with_sub_that_is_not_uuid_returns_401():
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": "abc", "exp": exp},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_token_bearerAuth(_bearer(token))

    assert exc_info.value.status_code == 401
