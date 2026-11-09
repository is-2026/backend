# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.user_api_base import BaseUserApi
import app.impl

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.models.user import User

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from typing import Any
from app.models.change_password_input import ChangePasswordInput
from app.models.error import Error
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)

@router.get(
    "/user",
    responses={
        200: {"model": User, "description": "Datos de la cuenta"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["User"],
    summary="Obtener mi usuario",
    response_model_by_alias=True,
)

async def get_my_user(
     token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not BaseUserApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    user_id = UUID(token_bearerAuth.sub)
    return await BaseUserApi.subclasses[0](session).get_my_user(user_id)

@router.patch(
    "/user/password",
    responses={
        200: {"description": "Contraseña actualizada"},
        400: {"model": Error, "description": "La contraseña actual es incorrecta, o la nueva coincide con la actual"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["User"],
    summary="Modificar contraseña",
    response_model_by_alias=True,
)
async def change_password(
    change_password_input: ChangePasswordInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseUserApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseUserApi.subclasses[0]().change_password(change_password_input)
