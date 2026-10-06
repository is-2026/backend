# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.players_api_base import BasePlayersApi
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
from app.models.create_player_input import CreatePlayerInput
from app.models.error import Error
from app.models.player import Player
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth
from app.db.club import ClubDB
from app.dependencies import get_current_club

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/club/players",
    responses={
        200: {"model": List[Player], "description": "Plantilla completa del club"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Players"],
    summary="Listar jugadores del club",
    response_model_by_alias=True,
)
async def list_my_players(
    club: ClubDB = Security(get_current_club),
) -> List[Player]:
    if not BasePlayersApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePlayersApi.subclasses[0]().list_my_players(club.id)


@router.post(
    "/club/players",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": Player, "description": "Jugador creado exitosamente"},
        400: {"model": Error, "description": "El número de camiseta de jugdor está fuera de rango (1-99), la suma de los PACSS no es 300, o alguno está fuera de rango (20-100)"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        409: {"model": Error, "description": "El número de camiseta de jugdor está en uso."},
    },
    tags=["Players"],
    summary="Crear jugador",
    response_model_by_alias=True,
)
async def create_player(
    create_player_input: CreatePlayerInput = Body(..., description=""),
    club: ClubDB = Security(get_current_club),
) -> Player:
    """Crea un nuevo jugador en el club del usuario. Notar que la suma de sus PACSS debe ser exactamente 300."""
    if not BasePlayersApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePlayersApi.subclasses[0]().create_player(create_player_input, club.id)


@router.get(
    "/club/players/{player_id}",
    responses={
        200: {"model": Player, "description": "Datos del jugador"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Players"],
    summary="Obtener jugador",
    response_model_by_alias=True,
)
async def get_my_player(
    player_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Player:
    if not BasePlayersApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePlayersApi.subclasses[0]().get_my_player(player_id)


@router.delete(
    "/club/players/{player_id}",
    responses={
        200: {"description": "Jugador eliminado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El jugador está participando en una liga activa o un partido en curso"},
    },
    tags=["Players"],
    summary="Eliminar jugador",
    response_model_by_alias=True,
)
async def delete_player(
    player_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BasePlayersApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BasePlayersApi.subclasses[0]().delete_player(player_id)
