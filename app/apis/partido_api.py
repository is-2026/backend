# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.partido_api_base import BasePartidoApi
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
from app.models.cambiar_comportamiento_en_vivo_request import CambiarComportamientoEnVivoRequest
from app.models.enviar_alineacion_input import EnviarAlineacionInput
from app.models.error import Error
from app.models.partido import Partido
from app.models.programar_sustitucion_input import ProgramarSustitucionInput
from app.models.sustitucion import Sustitucion
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/partidos/{partido_id}",
    responses={
        200: {"model": Partido, "description": "Detalle del partido"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Partido"],
    summary="Obtener detalle de un partido",
    response_model_by_alias=True,
)
async def obtener_partido(
    partido_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Partido:
    """Devuelve la información actualizada de un partido específico, incluyendo su estado y resultado actual."""
    if not BasePartidoApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePartidoApi.subclasses[0]().obtener_partido(partido_id)


@router.post(
    "/partidos/{partido_id}/alineacion",
    responses={
        200: {"model": Partido, "description": "Alineación registrada"},
        400: {"model": Error, "description": "Alguno de los jugadores no pertenece al pool de convocados, o no se enviaron exactamente 3 titulares y 3 suplentes."},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Partido"],
    summary="Definir nuevos titulares, sus comportamientos y la formación antes de jugar el partido.",
    response_model_by_alias=True,
)
async def definir_alineacion(
    partido_id: UUID = Path(..., description=""),
    enviar_alineacion_input: EnviarAlineacionInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Partido:
    """Ventana de 30 segundos antes de cada partido (liga y amistoso). Los jugadores incluidos deben pertenecer al pool de convocados de la inscripción (liga) o el desafío/búsqueda (amistoso) correspondiente. Si no se completa a tiempo, el sistema asigna automáticamente los titulares/suplentes por defecto enviados al momento de inscribirse, los 3 comportamientos asignados a los jugadores por defecto, y la formación default del club."""
    if not BasePartidoApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePartidoApi.subclasses[0]().definir_alineacion(partido_id, enviar_alineacion_input)


@router.patch(
    "/partidos/{partido_id}/jugadores/{jugador_id}",
    responses={
        200: {"description": "Comportamiento actualizado"},
        400: {"model": Error, "description": "El comportamiento seleccionado fue eliminado o es inválido"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "El partido o el jugador indicado no existen"},
    },
    tags=["Partido"],
    summary="Cambiar comportamiento en vivo",
    response_model_by_alias=True,
)
async def cambiar_comportamiento_en_vivo(
    partido_id: UUID = Path(..., description=""),
    jugador_id: UUID = Path(..., description=""),
    cambiar_comportamiento_en_vivo_request: CambiarComportamientoEnVivoRequest = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Se aplica desde el siguiente tick del simulador."""
    if not BasePartidoApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePartidoApi.subclasses[0]().cambiar_comportamiento_en_vivo(partido_id, jugador_id, cambiar_comportamiento_en_vivo_request)


@router.post(
    "/partidos/{partido_id}/sustituciones",
    responses={
        201: {"model": Sustitucion, "description": "Sustitución programada"},
        400: {"model": Error, "description": "El jugador saliente no es titular actual, el jugador entrante no es suplente o no pertenecen a los 6 convocados."},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "Ya se agotaron los 3 cambios permitidos"},
    },
    tags=["Partido"],
    summary="Programar sustitución",
    response_model_by_alias=True,
)
async def programar_sustitucion(
    partido_id: UUID = Path(..., description=""),
    programar_sustitucion_input: ProgramarSustitucionInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Sustitucion:
    """Se agenda para la próxima ventana disponible (pausa de hidratación o entretiempo). Solo puede haber una sustitución pendiente por club a la vez."""
    if not BasePartidoApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePartidoApi.subclasses[0]().programar_sustitucion(partido_id, programar_sustitucion_input)


@router.delete(
    "/partidos/{partido_id}/sustituciones",
    responses={
        200: {"description": "Sustitución cancelada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "No hay ninguna sustitución pendiente"},
    },
    tags=["Partido"],
    summary="Desprogramar sustitución",
    response_model_by_alias=True,
)
async def desprogramar_sustitucion(
    partido_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Cancela la sustitución pendiente del club antes de que se alcance la ventana de cambio."""
    if not BasePartidoApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePartidoApi.subclasses[0]().desprogramar_sustitucion(partido_id)
