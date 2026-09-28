# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.jugadores_api_base import BaseJugadoresApi
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
from app.models.crear_jugador_input import CrearJugadorInput
from app.models.error import Error
from app.models.jugador import Jugador
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/club/jugadores",
    responses={
        200: {"model": List[Jugador], "description": "Plantilla completa del club"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Jugadores"],
    summary="Listar jugadores del club",
    response_model_by_alias=True,
)
async def listar_mis_jugadores(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> List[Jugador]:
    if not BaseJugadoresApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseJugadoresApi.subclasses[0]().listar_mis_jugadores()


@router.post(
    "/club/jugadores",
    responses={
        201: {"model": Jugador, "description": "Jugador creado exitosamente"},
        400: {"model": Error, "description": "El número de camiseta de jugdor está fuera de rango (1-99), la suma de los PACSS no es 300, o alguno está fuera de rango (20-100)"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        409: {"model": Error, "description": "El número de camiseta de jugdor está en uso."},
    },
    tags=["Jugadores"],
    summary="Crear jugador",
    response_model_by_alias=True,
)
async def crear_jugador(
    crear_jugador_input: CrearJugadorInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Jugador:
    """Crea un nuevo jugador en el club del usuario. Notar que la suma de sus PACSS debe ser exactamente 300."""
    if not BaseJugadoresApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseJugadoresApi.subclasses[0]().crear_jugador(crear_jugador_input)


@router.get(
    "/club/jugadores/{jugador_id}",
    responses={
        200: {"model": Jugador, "description": "Datos del jugador"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Jugadores"],
    summary="Obtener jugador",
    response_model_by_alias=True,
)
async def obtener_mi_jugador(
    jugador_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Jugador:
    if not BaseJugadoresApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseJugadoresApi.subclasses[0]().obtener_mi_jugador(jugador_id)


@router.delete(
    "/club/jugadores/{jugador_id}",
    responses={
        200: {"description": "Jugador eliminado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El jugador está participando en una liga activa o un partido en curso"},
    },
    tags=["Jugadores"],
    summary="Eliminar jugador",
    response_model_by_alias=True,
)
async def eliminar_jugador(
    jugador_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseJugadoresApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseJugadoresApi.subclasses[0]().eliminar_jugador(jugador_id)
