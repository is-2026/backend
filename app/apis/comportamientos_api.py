# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.comportamientos_api_base import BaseComportamientosApi
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
from app.models.comportamiento import Comportamiento
from app.models.crear_comportamiento_input import CrearComportamientoInput
from app.models.error import Error
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/club/comportamientos",
    responses={
        200: {"model": List[Comportamiento], "description": "Comportamientos disponibles (OK)"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Comportamientos"],
    summary="Listar comportamientos guardados",
    response_model_by_alias=True,
)
async def listar_comportamientos(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[Comportamiento]:
    if not BaseComportamientosApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseComportamientosApi.subclasses[0]().listar_comportamientos()


@router.post(
    "/club/comportamientos",
    responses={
        201: {"model": Comportamiento, "description": "Comportamiento creado"},
        400: {"model": Error, "description": "El código contiene errores de sintaxis o instrucciones prohibidas"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        409: {"model": Error, "description": "Nombre de comportamiento duplicado"},
    },
    tags=["Comportamientos"],
    summary="Crear nuevo Comportamiento",
    response_model_by_alias=True,
)
async def crear_comportamiento(
    crear_comportamiento_input: CrearComportamientoInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Comportamiento:
    if not BaseComportamientosApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseComportamientosApi.subclasses[0]().crear_comportamiento(crear_comportamiento_input)


@router.get(
    "/club/comportamientos/{comportamiento_id}",
    responses={
        200: {"model": Comportamiento, "description": "Detalle del comportamiento (OK)"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Comportamientos"],
    summary="Obtener comportamiento por id",
    response_model_by_alias=True,
)
async def obtener_comportamiento(
    comportamiento_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Comportamiento:
    if not BaseComportamientosApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseComportamientosApi.subclasses[0]().obtener_comportamiento(comportamiento_id)


@router.put(
    "/club/comportamientos/{comportamiento_id}",
    responses={
        200: {"model": Comportamiento, "description": "Comportamiento editado"},
        400: {"model": Error, "description": "El código contiene errores de sintaxis o instrucciones prohibidas"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El comportamiento está en uso por un jugador en un partido en curso, o el nuevo nombre ya está en uso por otro comportamiento"},
    },
    tags=["Comportamientos"],
    summary="Editar comportamiento",
    response_model_by_alias=True,
)
async def editar_comportamiento(
    comportamiento_id: UUID = Path(..., description=""),
    crear_comportamiento_input: CrearComportamientoInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Comportamiento:
    if not BaseComportamientosApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseComportamientosApi.subclasses[0]().editar_comportamiento(comportamiento_id, crear_comportamiento_input)


@router.delete(
    "/club/comportamientos/{comportamiento_id}",
    responses={
        200: {"description": "Comportamiento eliminado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El comportamiento está en uso por un jugador en un partido en curso"},
    },
    tags=["Comportamientos"],
    summary="Eliminar comportamiento",
    response_model_by_alias=True,
)
async def eliminar_comportamiento(
    comportamiento_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseComportamientosApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseComportamientosApi.subclasses[0]().eliminar_comportamiento(comportamiento_id)
