# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.usuario_api_base import BaseUsuarioApi
import app.impl

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
from app.models.cambiar_password_input import CambiarPasswordInput
from app.models.error import Error
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.patch(
    "/user/password",
    responses={
        200: {"description": "Contraseña actualizada"},
        400: {"model": Error, "description": "La contraseña actual es incorrecta, o la nueva coincide con la actual"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Usuario"],
    summary="Modificar contraseña",
    response_model_by_alias=True,
)
async def cambiar_password(
    cambiar_password_input: CambiarPasswordInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseUsuarioApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseUsuarioApi.subclasses[0]().cambiar_password(cambiar_password_input)
