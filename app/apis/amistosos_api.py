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

from pydantic import Field, field_validator
from typing import Any, List, Optional
from typing_extensions import Annotated
from uuid import UUID
from app.models.busqueda import Busqueda
from app.models.crear_busqueda_input import CrearBusquedaInput
from app.models.crear_desafio_input import CrearDesafioInput
from app.models.desafio import Desafio
from app.models.desafio_respuesta_input import DesafioRespuestaInput
from app.models.error import Error
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/amistosos/desafios",
    responses={
        200: {"model": List[Desafio], "description": "Desafíos del club"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Amistosos"],
    summary="Listar desafíos propios",
    response_model_by_alias=True,
)
async def listar_desafios(
    direccion: Annotated[Optional[str], Field(description="Filtra por desafíos enviados o recibidos por el club")] = Query(None, description="Filtra por desafíos enviados o recibidos por el club", alias="direccion"),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[Desafio]:
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().listar_desafios(direccion)


@router.post(
    "/amistosos/desafios",
    responses={
        201: {"model": Desafio, "description": "Desafío creado"},
        400: {"model": Error, "description": "No se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "El club rival indicado no existe"},
    },
    tags=["Amistosos"],
    summary="Enviar desafío amistoso",
    response_model_by_alias=True,
)
async def enviar_desafio(
    crear_desafio_input: CrearDesafioInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Desafio:
    """Incluye el pool de 6 convocados del club retador."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().enviar_desafio(crear_desafio_input)


@router.delete(
    "/amistosos/desafios/{desafio_id}",
    responses={
        200: {"description": "Desafío cancelado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El desafío ya fue respondido"},
    },
    tags=["Amistosos"],
    summary="Cancelar desafío enviado",
    response_model_by_alias=True,
)
async def cancelar_desafio(
    desafio_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    """Solo el club retador puede cancelarlo, y solo si sigue pendiente."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().cancelar_desafio(desafio_id)


@router.patch(
    "/amistosos/desafios/{desafio_id}",
    responses={
        200: {"model": Desafio, "description": "Desafío respondido"},
        400: {"model": Error, "description": "No se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        403: {"model": Error, "description": "El usuario no tiene permisos para realizar esta operación"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El desafío ya no está disponible"},
    },
    tags=["Amistosos"],
    summary="Responder desafío amistoso",
    response_model_by_alias=True,
)
async def responder_desafio(
    desafio_id: UUID = Path(..., description=""),
    desafio_respuesta_input: DesafioRespuestaInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Desafio:
    """Si se acepta, se debe incluir el pool de 6 convocados del club desafiado, y se crea el partido."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().responder_desafio(desafio_id, desafio_respuesta_input)


@router.post(
    "/amistosos/busqueda",
    responses={
        202: {"model": Busqueda, "description": "Búsqueda iniciada"},
        400: {"model": Error, "description": "No se enviaron exactamente 3 titulares y 3 suplentes"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        409: {"model": Error, "description": "El usuario ya está buscando partido"},
    },
    tags=["Amistosos"],
    summary="Iniciar búsqueda de rival (matchmaking público)",
    response_model_by_alias=True,
)
async def iniciar_matchmaking(
    crear_busqueda_input: CrearBusquedaInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Busqueda:
    """Devuelve el ticket nomás. La notificación de emparejamiento exitoso se recibe de forma asíncrona vía WebSocket en el canal &#x60;/ws/amistosos/busqueda&#x60; (ver especificación AsyncAPI, mensaje &#39;PartidoEncontrado&#39;)."""
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().iniciar_matchmaking(crear_busqueda_input)


@router.delete(
    "/amistosos/busqueda",
    responses={
        200: {"description": "Búsqueda cancelada"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "No hay ninguna búsqueda activa para cancelar"},
    },
    tags=["Amistosos"],
    summary="Cancelar búsqueda de rival",
    response_model_by_alias=True,
)
async def cancelar_matchmaking(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseAmistososApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseAmistososApi.subclasses[0]().cancelar_matchmaking()
