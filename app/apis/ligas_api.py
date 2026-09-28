# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.ligas_api_base import BaseLigasApi
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

from pydantic import field_validator
from typing import Any, List, Optional
from uuid import UUID
from app.models.crear_inscripcion_input import CrearInscripcionInput
from app.models.crear_liga_input import CrearLigaInput
from app.models.error import Error
from app.models.liga_detalle import LigaDetalle
from app.models.liga_resumen import LigaResumen
from app.models.partido import Partido
from app.models.tabla_posiciones_item import TablaPosicionesItem
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/ligas",
    responses={
        200: {"model": List[LigaDetalle], "description": "Ligas disponibles"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Ligas"],
    summary="Listar ligas",
    response_model_by_alias=True,
)
async def listar_ligas(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[LigaDetalle]:
    """Devuelve tanto ligas públicas como privadas. Solo no iniciadas"""
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().listar_ligas()


@router.post(
    "/ligas",
    responses={
        201: {"model": LigaDetalle, "description": "Liga creada"},
        400: {"model": Error, "description": "max_clubes excede el límite del sistema o no se enviaron enviaron exactamente 3 titulares (con sus comportamientos) y 3 suplentes en jugadores"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Ligas"],
    summary="Crear liga",
    response_model_by_alias=True,
)
async def crear_liga(
    crear_liga_input: CrearLigaInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> LigaDetalle:
    """Notar que la cantidad de clubes tiene un mínimo duro de 3. Si se envía password, la liga se considera privada."""
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().crear_liga(crear_liga_input)


@router.get(
    "/club/ligas",
    responses={
        200: {"model": List[LigaResumen], "description": "Ligas en las que participa mi club"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Ligas"],
    summary="Listar ligas de mi club",
    response_model_by_alias=True,
)
async def listar_mis_ligas(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[LigaResumen]:
    """Identifica al club mediante el token de sesión. Devuelve las ligas en las que el club está inscripto."""
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().listar_mis_ligas()


@router.get(
    "/ligas/{liga_id}",
    responses={
        200: {"model": LigaDetalle, "description": "Datos de la liga"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Ligas"],
    summary="Obtener detalle de una liga",
    response_model_by_alias=True,
)
async def obtener_liga(
    liga_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> LigaDetalle:
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().obtener_liga(liga_id)


@router.delete(
    "/ligas/{liga_id}",
    responses={
        200: {"description": "Liga cancelada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga ya se encuentra iniciada"},
    },
    tags=["Ligas"],
    summary="Cancelar liga",
    response_model_by_alias=True,
)
async def cancelar_liga(
    liga_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Solo el creador puede cancelarla, y solo si no está iniciada."""
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().cancelar_liga(liga_id)


@router.post(
    "/ligas/{liga_id}/inscripciones",
    responses={
        200: {"description": "Inscripción registrada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        400: {"model": Error, "description": "La contraseña de la liga privada es incorrecta, no hay cupo, o no se enviaron exactamente 3 titulares y 3 suplentes."},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El club ya está inscripto en esta liga"},
    },
    tags=["Ligas"],
    summary="Unirse a una liga",
    response_model_by_alias=True,
)
async def unirse_liga(
    liga_id: UUID = Path(..., description=""),
    crear_inscripcion_input: CrearInscripcionInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Reserva un cupo para la liga. Se definen 6 jugadores convocados para toda la liga (3 marcados como titulares por defecto, 3 como suplentes). Los titulares enviados se usan como fallback si el club no define la alineación antes de alguno de sus partidos."""
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().unirse_liga(liga_id, crear_inscripcion_input)


@router.delete(
    "/ligas/{liga_id}/inscripciones",
    responses={
        200: {"description": "Inscripción eliminada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "La liga indicada no existe, o el club no está inscripto en ella"},
        409: {"model": Error, "description": "La liga ya se encuentra iniciada"},
    },
    tags=["Ligas"],
    summary="Abandonar liga",
    response_model_by_alias=True,
)
async def abandonar_liga(
    liga_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().abandonar_liga(liga_id)


@router.post(
    "/ligas/{liga_id}/inicio",
    responses={
        200: {"model": LigaDetalle, "description": "Liga iniciada"},
        400: {"model": Error, "description": "No hay suficientes clubes inscriptos para iniciar la liga"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga ya se encuentra iniciada"},
    },
    tags=["Ligas"],
    summary="Iniciar liga",
    response_model_by_alias=True,
)
async def iniciar_liga(
    liga_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> LigaDetalle:
    """Solo el creador puede iniciarla. Cambia el estado a \&quot;iniciada\&quot; y genera el fixture."""
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().iniciar_liga(liga_id)


@router.get(
    "/ligas/{liga_id}/partidos",
    responses={
        200: {"model": List[Partido], "description": "Partidos de la liga"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga aún no fue iniciada"},
    },
    tags=["Ligas"],
    summary="Listar partidos de una liga",
    response_model_by_alias=True,
)
async def listar_partidos_liga(
    liga_id: UUID = Path(..., description=""),
    estado: Optional[str] = Query(None, description="", alias="estado"),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[Partido]:
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().listar_partidos_liga(liga_id, estado)


@router.get(
    "/ligas/{liga_id}/tabla",
    responses={
        200: {"model": List[TablaPosicionesItem], "description": "Tabla de posiciones de la liga"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga aún no fue iniciada"},
    },
    tags=["Ligas"],
    summary="Tabla de posiciones",
    response_model_by_alias=True,
)
async def obtener_tabla(
    liga_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[TablaPosicionesItem]:
    if not BaseLigasApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLigasApi.subclasses[0]().obtener_tabla(liga_id)
