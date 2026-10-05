# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.friendlies_api_base import BaseFriendliesApi
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

from typing import Any, List
from uuid import UUID
from app.models.create_friendly_input import CreateFriendlyInput
from app.models.error import Error
from app.models.friendly import Friendly
from app.models.join_friendly_input import JoinFriendlyInput
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.db.club import ClubDB
from app.dependencies import get_current_club
from app.dependencies import get_current_club, get_lobby_manager
from app.ws.connection_manager import ConnectionManager

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/friendlies",
    responses={
        200: {"model": List[Friendly], "description": "Lista de amistosos disponibles"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Friendlies"],
    summary="Listar amistosos",
    response_model_by_alias=True,
)
async def list_friendlies(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
    session: AsyncSession = Depends(get_session),
    lobby: ConnectionManager = Depends(get_lobby_manager)
) -> List[Friendly]:
    """Devuelve una lista de amistosos que están esperando rival, incluyendo públicos y privados."""
    if not BaseFriendliesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseFriendliesApi.subclasses[0](session, lobby).list_friendlies()


@router.post(
    "/friendlies",
    responses={
        201: {"model": Friendly, "description": "Amistoso creado"},
        400: {"model": Error, "description": "No se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Friendlies"],
    summary="Crear amistoso",
    response_model_by_alias=True,
)
async def create_friendly(
    create_friendly_input: CreateFriendlyInput = Body(..., description=""),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
    lobby: ConnectionManager = Depends(get_lobby_manager)
) -> Friendly:
    """Crea un amistoso esperando por un rival. Si se envía password, el amistoso se marca como privado."""
    if not BaseFriendliesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseFriendliesApi.subclasses[0](session, lobby).create_friendly(create_friendly_input, club.id)


@router.post(
    "/friendlies/{friendly_id}/join",
    responses={
        200: {"model": Friendly, "description": "Unido al amistoso exitosamente"},
        400: {"model": Error, "description": "Contraseña incorrecta o no se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El amistoso ya no está disponible (ya tiene rival o fue cancelado)"},
    },
    tags=["Friendlies"],
    summary="Unirse a un amistoso",
    response_model_by_alias=True,
)
async def join_friendly(
    friendly_id: UUID = Path(..., description=""),
    join_friendly_input: JoinFriendlyInput = Body(..., description=""),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
    lobby: ConnectionManager = Depends(get_lobby_manager)
) -> Friendly:
    """Se une a un amistoso creado por otro club. Si es privado, requiere la contraseña. Al unirse exitosamente, se genera el partido."""
    if not BaseFriendliesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseFriendliesApi.subclasses[0](session, lobby).join_friendly(friendly_id, join_friendly_input, club.id)


@router.delete(
    "/friendlies/{friendly_id}",
    responses={
        200: {"description": "Amistoso cancelado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El amistoso ya tiene un rival y no puede ser cancelado"},
    },
    tags=["Friendlies"],
    summary="Cancelar amistoso",
    response_model_by_alias=True,
)
async def cancel_friendly(
    friendly_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Solo el club creador puede cancelarlo, y solo si aún no se ha unido ningún rival."""
    if not BaseFriendliesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseFriendliesApi.subclasses[0]().cancel_friendly(friendly_id)
