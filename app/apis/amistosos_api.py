# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.amistosos_api_base import BaseAmistososApi
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
from app.models.amistoso import Amistoso
from app.models.crear_amistoso_input import CrearAmistosoInput
from app.models.error import Error
from app.models.unirse_amistoso_input import UnirseAmistosoInput
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/amistosos",
    responses={
        200: {"model": List[Amistoso], "description": "Lista de amistosos disponibles"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Amistosos"],
    summary="Listar amistosos",
    response_model_by_alias=True,
)
async def listar_amistosos(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[Amistoso]:
    """Devuelve una lista de amistosos que están esperando rival, incluyendo públicos y privados."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().listar_amistosos()


@router.post(
    "/amistosos",
    responses={
        201: {"model": Amistoso, "description": "Amistoso creado"},
        400: {"model": Error, "description": "No se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Amistosos"],
    summary="Crear amistoso",
    response_model_by_alias=True,
)
async def crear_amistoso(
    crear_amistoso_input: CrearAmistosoInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Amistoso:
    """Crea un amistoso esperando por un rival. Si se envía password, el amistoso se marca como privado."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().crear_amistoso(crear_amistoso_input)


@router.post(
    "/amistosos/{amistoso_id}/unirse",
    responses={
        200: {"model": Amistoso, "description": "Unido al amistoso exitosamente"},
        400: {"model": Error, "description": "Contraseña incorrecta o no se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El amistoso ya no está disponible (ya tiene rival o fue cancelado)"},
    },
    tags=["Amistosos"],
    summary="Unirse a un amistoso",
    response_model_by_alias=True,
)
async def unirse_amistoso(
    amistoso_id: UUID = Path(..., description=""),
    unirse_amistoso_input: UnirseAmistosoInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Amistoso:
    """Se une a un amistoso creado por otro club. Si es privado, requiere la contraseña. Al unirse exitosamente, se genera el partido."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().unirse_amistoso(amistoso_id, unirse_amistoso_input)


@router.delete(
    "/amistosos/{amistoso_id}",
    responses={
        200: {"description": "Amistoso cancelado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El amistoso ya tiene un rival y no puede ser cancelado"},
    },
    tags=["Amistosos"],
    summary="Cancelar amistoso",
    response_model_by_alias=True,
)
async def cancelar_amistoso(
    amistoso_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Solo el club creador puede cancelarlo, y solo si aún no se ha unido ningún rival."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().cancelar_amistoso(amistoso_id)
