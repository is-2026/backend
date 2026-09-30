# coding: utf-8

import uuid
from typing import List

import jwt
from fastapi import Depends, HTTPException, Security, status  # noqa: F401
from fastapi.openapi.models import OAuthFlowImplicit, OAuthFlows  # noqa: F401
from fastapi.security import (  # noqa: F401
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
    OAuth2,
    OAuth2AuthorizationCodeBearer,
    OAuth2PasswordBearer,
    SecurityScopes,
)
from fastapi.security.api_key import (  # noqa: F401
    APIKeyCookie,
    APIKeyHeader,
    APIKeyQuery,
)

from app.models.extra_models import TokenModel
from app.security.tokens import decode_access_token

bearer_auth = HTTPBearer(auto_error=False)


def get_token_bearerAuth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_auth),
) -> TokenModel:
    """
    Check and retrieve authentication information from custom bearer token.

    :param credentials Credentials provided by Authorization header
    :type credentials: HTTPAuthorizationCredentials | None
    :return: Decoded token information or None if token is invalid
    :rtype: TokenModel
    """
    if not credentials:
        raise _unauthorized()
    try:
        token = decode_access_token(credentials.credentials)
        uuid.UUID(token["sub"])
    except (jwt.InvalidTokenError, ValueError) as e:
        raise _unauthorized() from e
    return TokenModel(sub=token["sub"])


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado: No se proporcionó un token, o el token es inválido o expiró",
        headers={"WWW-Authenticate": "Bearer"},
    )
