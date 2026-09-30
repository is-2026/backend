import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
from app.security.tokens import create_access_token, decode_access_token


def _sign(payload: dict, secret: str | None = None, algorithm: str = "HS256") -> str:
    """Arma un token a mano, para probar qué acepta y qué rechaza decode."""
    if secret is None:
        secret = get_settings().jwt_secret
    return jwt.encode(payload, secret, algorithm=algorithm)


def _in(minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


# para create_access_token
def test_token_contains_user_id_in_sub():
    user_id = uuid.uuid4()

    token = decode_access_token(create_access_token(user_id))

    assert token["sub"] == str(user_id)


def test_token_expires(monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "15")
    get_settings.cache_clear()

    token = decode_access_token(create_access_token(uuid.uuid4()))

    assert token["exp"] - token["iat"] == 15 * 60


def test_token_is_signed_with_configured_algorithm():
    token = create_access_token(uuid.uuid4())

    assert jwt.get_unverified_header(token)["alg"] == "HS256"


# para decode_access_token
def test_rejects_expired_token():
    token = _sign({"sub": "abc", "exp": _in(-1)})

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_rejects_token_signed_with_another_secret():
    token = _sign({"sub": "abc", "exp": _in(5)}, secret="another-secret-" + "y" * 32)

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token)


def test_rejects_token_without_exp():
    token = _sign({"sub": "abc"})

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)


def test_rejects_token_without_sub():
    token = _sign({"exp": _in(5)})

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)


def test_rejects_token_signed_with_another_algorithm():
    token = _sign({"sub": "abc", "exp": _in(5)}, algorithm="HS512")

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(token)


def test_rejects_token_without_signature_alg_none():
    token = jwt.encode({"sub": "abc", "exp": _in(5)}, key=None, algorithm="none")

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(token)


def test_rejects_invalid_token_format():
    with pytest.raises(jwt.DecodeError):
        decode_access_token("this-is-not-a-jwt")
