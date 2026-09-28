# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.autenticacin_api_base import BaseAutenticacinApi
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
from app.models.auth_login_input import AuthLoginInput
from app.models.auth_response import AuthResponse
from app.models.error import Error
from app.models.usuario_registro_input import UsuarioRegistroInput
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.post(
    "/auth/registro",
    responses={
        201: {"model": AuthResponse, "description": "Usuario registrado exitosamente"},
        400: {"model": Error, "description": "Solicitud inválida"},
        409: {"model": Error, "description": "El email ya está registrado"},
    },
    tags=["Autenticación"],
    summary="Registrar Usuario",
    response_model_by_alias=True,
)
async def registrar_usuario(
    usuario_registro_input: UsuarioRegistroInput = Body(..., description=""),
) -> AuthResponse:
    """Crea la cuenta de usuario. El club se crea en un paso separado (POST /club) inmediatamente después, dentro del mismo flujo de onboarding del cliente."""
    if not BaseAutenticacinApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAutenticacinApi.subclasses[0]().registrar_usuario(usuario_registro_input)


@router.post(
    "/auth/login",
    responses={
        200: {"model": AuthResponse, "description": "Sesión iniciada"},
        400: {"model": Error, "description": "Solicitud inválida"},
        401: {"model": Error, "description": "Email o contraseña incorrectos"},
    },
    tags=["Autenticación"],
    summary="Iniciar sesion",
    response_model_by_alias=True,
)
async def iniciar_sesion(
    auth_login_input: AuthLoginInput = Body(..., description=""),
) -> AuthResponse:
    if not BaseAutenticacinApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAutenticacinApi.subclasses[0]().iniciar_sesion(auth_login_input)


@router.post(
    "/auth/logout",
    responses={
        200: {"description": "Sesión cerrada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Autenticación"],
    summary="Cerrar sesión",
    response_model_by_alias=True,
)
async def cerrar_sesion(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseAutenticacinApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAutenticacinApi.subclasses[0]().cerrar_sesion()
