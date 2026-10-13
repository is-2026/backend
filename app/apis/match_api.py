# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.match_api_base import BaseMatchApi
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
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.models.change_live_behavior_request import ChangeLiveBehaviorRequest
from app.models.error import Error
from app.models.match import Match
from app.models.schedule_substitution_input import ScheduleSubstitutionInput
from app.models.submit_lineup_input import SubmitLineupInput
from app.models.substitution import Substitution
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/matches/{match_id}",
    responses={
        200: {"model": Match, "description": "Detalle del partido"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Match"],
    summary="Obtener detalle de un partido",
    response_model_by_alias=True,
)
async def get_match(
    match_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
    session: AsyncSession = Depends(get_session),
) -> Match:
    """Devuelve la información actualizada de un partido específico, incluyendo su estado y resultado actual."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0](session).get_match(match_id)


@router.post(
    "/matches/{match_id}/lineup",
    responses={
        200: {"model": Match, "description": "Alineación registrada"},
        400: {"model": Error, "description": "Alguno de los jugadores no pertenece al pool de convocados, o no se enviaron exactamente 3 titulares y 3 suplentes."},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Match"],
    summary="Definir nuevos titulares, sus comportamientos y la formación antes de jugar el partido.",
    response_model_by_alias=True,
)
async def set_lineup(
    match_id: UUID = Path(..., description=""),
    submit_lineup_input: SubmitLineupInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Match:
    """Ventana de 30 segundos antes de cada partido (liga y amistoso). Los jugadores incluidos deben pertenecer al pool de convocados de la inscripción (liga) o el desafío/búsqueda (amistoso) correspondiente. Si no se completa a tiempo, el sistema asigna automáticamente los titulares/suplentes por defecto enviados al momento de inscribirse, los 3 comportamientos asignados a los jugadores por defecto, y la formación default del club."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0]().set_lineup(match_id, submit_lineup_input)


@router.patch(
    "/matches/{match_id}/players/{player_id}",
    responses={
        200: {"description": "Comportamiento actualizado"},
        400: {"model": Error, "description": "El comportamiento seleccionado fue eliminado o es inválido"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "El partido o el jugador indicado no existen"},
    },
    tags=["Match"],
    summary="Cambiar comportamiento en vivo",
    response_model_by_alias=True,
)
async def change_live_behavior(
    match_id: UUID = Path(..., description=""),
    player_id: UUID = Path(..., description=""),
    change_live_behavior_request: ChangeLiveBehaviorRequest = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Se aplica desde el siguiente tick del simulador."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0]().change_live_behavior(match_id, player_id, change_live_behavior_request)


@router.post(
    "/matches/{match_id}/substitutions",
    responses={
        201: {"model": Substitution, "description": "Sustitución programada"},
        400: {"model": Error, "description": "El jugador saliente no es titular actual, el jugador entrante no es suplente o no pertenecen a los 6 convocados."},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "Ya se agotaron los 3 cambios permitidos"},
    },
    tags=["Match"],
    summary="Programar sustitución",
    response_model_by_alias=True,
)
async def schedule_substitution(
    match_id: UUID = Path(..., description=""),
    schedule_substitution_input: ScheduleSubstitutionInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Substitution:
    """Se agenda para la próxima ventana disponible (pausa de hidratación o entretiempo). Solo puede haber una sustitución pendiente por club a la vez."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0]().schedule_substitution(match_id, schedule_substitution_input)


@router.delete(
    "/matches/{match_id}/substitutions",
    responses={
        200: {"description": "Sustitución cancelada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "No hay ninguna sustitución pendiente"},
    },
    tags=["Match"],
    summary="Desprogramar sustitución",
    response_model_by_alias=True,
)
async def unschedule_substitution(
    match_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Cancela la sustitución pendiente del club antes de que se alcance la ventana de cambio."""
    if not BaseMatchApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseMatchApi.subclasses[0]().unschedule_substitution(match_id)
