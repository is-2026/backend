# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.club_api_base import BaseClubApi
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

from typing import List
from uuid import UUID
from app.models.cambiar_avatar_input import CambiarAvatarInput
from app.models.cambiar_formacion_default_input import CambiarFormacionDefaultInput
from app.models.club import Club
from app.models.crear_club_input import CrearClubInput
from app.models.error import Error
from app.models.historial_item import HistorialItem
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/club",
    responses={
        200: {"model": Club, "description": "Datos del club propio"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Club"],
    summary="Obtener mi club",
    response_model_by_alias=True,
)
async def obtener_mi_club(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Club:
    """Identifica al club mediante el token de sesión."""
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().obtener_mi_club()


@router.post(
    "/club",
    responses={
        201: {"model": Club, "description": "Club creado"},
        400: {"model": Error, "description": "Falta alguno de los dos campos o las entradas son inválidas."},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        409: {"model": Error, "description": "El usuario ya tiene un club creado"},
    },
    tags=["Club"],
    summary="Crear club (segundo paso del registro)",
    response_model_by_alias=True,
)
async def crear_club(
    crear_club_input: CrearClubInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Club:
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().crear_club(crear_club_input)


@router.patch(
    "/club/avatar",
    responses={
        200: {"model": Club, "description": "Avatar actualizado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Club"],
    summary="Cambiar avatar del club",
    response_model_by_alias=True,
)
async def cambiar_avatar(
    cambiar_avatar_input: CambiarAvatarInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Club:
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().cambiar_avatar(cambiar_avatar_input)


@router.patch(
    "/club/formacion",
    responses={
        200: {"model": Club, "description": "Formación default actualizada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Club"],
    summary="Cambiar formación default del club",
    response_model_by_alias=True,
)
async def cambiar_formacion_default(
    cambiar_formacion_default_input: CambiarFormacionDefaultInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Club:
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().cambiar_formacion_default(cambiar_formacion_default_input)


@router.get(
    "/club/historial",
    responses={
        200: {"model": List[HistorialItem], "description": "Historial de partidos jugados"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Club"],
    summary="Ver historial de partidos de mi club",
    response_model_by_alias=True,
)
async def obtener_mi_historial(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[HistorialItem]:
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().obtener_mi_historial()


@router.get(
    "/clubes/{club_id}/historial",
    responses={
        200: {"model": List[HistorialItem], "description": "Historial de partidos entre ambos clubes"},
        400: {"model": Error, "description": "No se puede consultar el historial compartido con el propio club"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Club"],
    summary="Ver historial compartido con otro club",
    response_model_by_alias=True,
)
async def obtener_historial_compartido(
    club_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[HistorialItem]:
    """Historial de partidos jugados entre el club del usuario autenticado y el club indicado."""
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().obtener_historial_compartido(club_id)


@router.get(
    "/clubes/{club_id}",
    responses={
        200: {"model": Club, "description": "Datos públicos del club"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Club"],
    summary="Ver club de un usuario",
    response_model_by_alias=True,
)
async def obtener_club(
    club_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Club:
    if not BaseClubApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseClubApi.subclasses[0]().obtener_club(club_id)
