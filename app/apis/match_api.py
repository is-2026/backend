# coding: utf-8

import importlib
import pkgutil
from typing import Any, Dict, List  # noqa: F401
from uuid import UUID

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
from sqlalchemy.ext.asyncio import AsyncSession

import app.impl
from app.apis.match_api_base import BaseMatchApi
from app.db.club import ClubDB
from app.db.session import get_session
from app.dependencies import get_current_club
from app.models.change_live_behavior_request import ChangeLiveBehaviorRequest
from app.models.error import Error
from app.models.extra_models import TokenModel  # noqa: F401
from app.models.match import Match
from app.models.schedule_substitution_input import ScheduleSubstitutionInput
from app.models.substitution import Substitution
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/matches/{match_id}",
    responses={
        200: {"model": Match, "description": "Detalle del partido"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Match"],
    summary="Obtener detalle de un partido",
    response_model_by_alias=True,
)
async def get_match(
    match_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    session: AsyncSession = Depends(get_session),
) -> Match:
    """Devuelve la información actualizada de un partido específico,
    incluyendo su estado y resultado actual.
    """
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0](session).get_match(match_id)


@router.patch(
    "/matches/{match_id}/players/{player_id}",
    responses={
        200: {"description": "Comportamiento actualizado"},
        400: {
            "model": Error,
            "description": "El comportamiento seleccionado fue eliminado o es inválido",
        },
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        403: {
            "model": Error,
            "description": "El usuario no tiene permisos para realizar esta operación",
        },
        404: {
            "model": Error,
            "description": "El partido o el jugador indicado no existen",
        },
        409: {
            "model": Error,
            "description": "El partido se encuentra en penales"
        }
    },
    tags=["Match"],
    summary="Cambiar comportamiento en vivo",
    response_model_by_alias=True,
)
async def change_live_behavior(
    match_id: UUID = Path(..., description=""),
    player_id: UUID = Path(..., description=""),
    change_live_behavior_request: ChangeLiveBehaviorRequest = Body(..., description=""),
    club: ClubDB = Security(get_current_club),
    session : AsyncSession = Depends(get_session)
) -> None:
    """Se aplica desde el siguiente tick del simulador."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0](session).change_live_behavior(
        match_id, player_id, change_live_behavior_request, club.id
    )


@router.post(
    "/matches/{match_id}/substitutions",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "model": Substitution,
            "description": "Sustitución programada para la próxima pausa o la pausa en curso",
        },
        400: {
            "model": Error,
            "description": "El jugador que sale no está en la cancha, el que entra no está en el banco o el comportamiento no existe",
        },
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        403: {
            "model": Error,
            "description": "El club del usuario no juega ese partido",
        },
        404: {"model": Error, "description": "El partido no está en juego"},
        409: {
            "model": Error,
            "description": "Ya hay una sustitución pendiente o no quedan pausas",
        },
    },
    tags=["Match"],
    summary="Programar sustitución",
    response_model_by_alias=True,
)
async def schedule_substitution(
    match_id: UUID = Path(..., description=""),
    schedule_substitution_input: ScheduleSubstitutionInput = Body(..., description=""),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> Substitution:
    """Cambia un titular por un suplente con el comportamiento elegido. 
    Se ejecuta al terminar la próxima pausa, o la pausa en curso si se pide durante una.
    Solo puede haber una pendiente por club.
    """
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0](session).schedule_substitution(
        match_id, schedule_substitution_input, club.id
    )


@router.delete(
    "/matches/{match_id}/substitutions",
    responses={
        200: {"description": "Sustitución cancelada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El club del usuario no juega ese partido"},
        404: {"model": Error, "description": "El partido no está en juego o no hay ninguna sustitución pendiente"},
    },
    tags=["Match"],
    summary="Desprogramar sustitución",
    response_model_by_alias=True,
)
async def unschedule_substitution(
    match_id: UUID = Path(..., description=""),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Cancela la sustitución pendiente del club antes de que se ejecute."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0](session).unschedule_substitution(
        match_id, club.id
    )
