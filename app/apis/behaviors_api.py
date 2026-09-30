# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.behaviors_api_base import BaseBehaviorsApi
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
from app.models.behavior import Behavior
from app.models.create_behavior_input import CreateBehaviorInput
from app.models.error import Error
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/club/behaviors",
    responses={
        200: {"model": List[Behavior], "description": "Comportamientos disponibles (OK)"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Behaviors"],
    summary="Listar comportamientos guardados",
    response_model_by_alias=True,
)
async def list_behaviors(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
    session: AsyncSession = Depends(get_session),
) -> List[Behavior]:
    if not BaseBehaviorsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseBehaviorsApi.subclasses[0](session).list_behaviors()


@router.post(
    "/club/behaviors",
    responses={
        201: {"model": Behavior, "description": "Comportamiento creado"},
        400: {"model": Error, "description": "El código contiene errores de sintaxis o instrucciones prohibidas"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        409: {"model": Error, "description": "Nombre de comportamiento duplicado"},
    },
    tags=["Behaviors"],
    summary="Crear nuevo Comportamiento",
    response_model_by_alias=True,
)
async def create_behavior(
    create_behavior_input: CreateBehaviorInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Behavior:
    if not BaseBehaviorsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseBehaviorsApi.subclasses[0]().create_behavior(create_behavior_input)


@router.get(
    "/club/behaviors/{behavior_id}",
    responses={
        200: {"model": Behavior, "description": "Detalle del comportamiento (OK)"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Behaviors"],
    summary="Obtener comportamiento por id",
    response_model_by_alias=True,
)
async def get_behavior(
    behavior_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
    session: AsyncSession = Depends(get_session),
) -> Behavior:
    if not BaseBehaviorsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseBehaviorsApi.subclasses[0](session).get_behavior(behavior_id)


@router.put(
    "/club/behaviors/{behavior_id}",
    responses={
        200: {"model": Behavior, "description": "Comportamiento editado"},
        400: {"model": Error, "description": "El código contiene errores de sintaxis o instrucciones prohibidas"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El comportamiento está en uso por un jugador en un partido en curso, o el nuevo nombre ya está en uso por otro comportamiento"},
    },
    tags=["Behaviors"],
    summary="Editar comportamiento",
    response_model_by_alias=True,
)
async def update_behavior(
    behavior_id: UUID = Path(..., description=""),
    create_behavior_input: CreateBehaviorInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> Behavior:
    if not BaseBehaviorsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseBehaviorsApi.subclasses[0]().update_behavior(behavior_id, create_behavior_input)


@router.delete(
    "/club/behaviors/{behavior_id}",
    responses={
        200: {"description": "Comportamiento eliminado"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El comportamiento está en uso por un jugador en un partido en curso"},
    },
    tags=["Behaviors"],
    summary="Eliminar comportamiento",
    response_model_by_alias=True,
)
async def delete_behavior(
    behavior_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ),
) -> None:
    if not BaseBehaviorsApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseBehaviorsApi.subclasses[0]().delete_behavior(behavior_id)
