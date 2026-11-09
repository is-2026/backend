# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.leagues_api_base import BaseLeaguesApi
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
from app.models.create_league_input import CreateLeagueInput
from app.models.error import Error
from app.models.join_league_input import JoinLeagueInput
from app.models.league_detail import LeagueDetail
from app.models.league_summary import LeagueSummary
from app.models.match import Match
from app.models.standings_item import StandingsItem
from app.models.submit_lineup_input import SubmitLineupInput
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth
from app.db.session import get_session
from app.db.club import ClubDB
from app.dependencies import get_current_club, get_league_scheduler
from app.ws.league_scheduler import LeagueScheduler
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/leagues",
    responses={
        200: {"model": List[LeagueDetail], "description": "Ligas disponibles"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
    },
    tags=["Leagues"],
    summary="Listar ligas",
    response_model_by_alias=True,
)
async def list_leagues(
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    session: AsyncSession = Depends(get_session),
) -> List[LeagueDetail]:
    """Devuelve tanto ligas públicas como privadas. Solo no iniciadas"""
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).list_leagues()


@router.post(
    "/leagues",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": LeagueDetail, "description": "Liga creada"},
        400: {
            "model": Error,
            "description": "max_clubs excede el límite del sistema o no se enviaron enviaron exactamente 3 titulares (con sus comportamientos) y 3 suplentes en players",
        },
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
    },
    tags=["Leagues"],
    summary="Crear liga",
    response_model_by_alias=True,
)
async def create_league(
    create_league_input: CreateLeagueInput = Body(..., description=""),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> LeagueDetail:
    """Notar que la cantidad de clubes tiene un mínimo duro de 3. Si se envía password, la liga se considera privada."""
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).create_league(
        create_league_input, club
    )


@router.get(
    "/club/leagues",
    responses={
        200: {
            "model": List[LeagueSummary],
            "description": "Ligas en las que participa mi club",
        },
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
    },
    tags=["Leagues"],
    summary="Listar ligas de mi club",
    response_model_by_alias=True,
)
async def list_my_leagues(
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> List[LeagueSummary]:
    """Identifica al club mediante el token de sesión. Devuelve las ligas en las que el club está inscripto."""
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).list_my_leagues(club.id)


@router.get(
    "/leagues/{league_id}",
    responses={
        200: {"model": LeagueDetail, "description": "Datos de la liga"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Leagues"],
    summary="Obtener detalle de una liga",
    response_model_by_alias=True,
)
async def get_league(
    league_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    session: AsyncSession = Depends(get_session),
) -> LeagueDetail:
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).get_league(league_id)


@router.delete(
    "/leagues/{league_id}",
    responses={
        200: {"description": "Liga cancelada"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        403: {
            "model": Error,
            "description": "El usuario no tiene permisos para realizar esta operación",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga ya se encuentra iniciada"},
    },
    tags=["Leagues"],
    summary="Cancelar liga",
    response_model_by_alias=True,
)
async def cancel_league(
    league_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
) -> None:
    """Solo el creador puede cancelarla, y solo si no está iniciada."""
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0]().cancel_league(league_id)


@router.post(
    "/leagues/{league_id}/join",
    responses={
        200: {"description": "Inscripción registrada"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        400: {
            "model": Error,
            "description": "La contraseña de la liga privada es incorrecta, no hay cupo, o no se enviaron exactamente 3 titulares y 3 suplentes.",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "El club ya está inscripto en esta liga"},
    },
    tags=["Leagues"],
    summary="Unirse a una liga",
    response_model_by_alias=True,
)
async def join_league(
    league_id: UUID = Path(..., description=""),
    join_league_input: JoinLeagueInput = Body(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Reserva un cupo para la liga. Se definen 6 jugadores convocados para toda la liga (3 marcados como titulares por defecto, 3 como suplentes). Los titulares enviados se usan como fallback si el club no define la alineación antes de alguno de sus partidos."""
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).join_league(
        league_id, join_league_input, club
    )


@router.delete(
    "/leagues/{league_id}/join",
    responses={
        200: {"description": "Inscripción eliminada"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        404: {
            "model": Error,
            "description": "La liga indicada no existe, o el club no está inscripto en ella",
        },
        409: {"model": Error, "description": "La liga ya se encuentra iniciada"},
    },
    tags=["Leagues"],
    summary="Abandonar liga",
    response_model_by_alias=True,
)
async def leave_league(
    league_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).leave_league(league_id, club)


@router.post(
    "/leagues/{league_id}/start",
    responses={
        200: {"model": LeagueDetail, "description": "Liga iniciada"},
        400: {
            "model": Error,
            "description": "No hay suficientes clubes inscriptos para iniciar la liga",
        },
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        403: {
            "model": Error,
            "description": "El usuario no tiene permisos para realizar esta operación",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga ya se encuentra iniciada"},
    },
    tags=["Leagues"],
    summary="Iniciar liga",
    response_model_by_alias=True,
)
async def start_league(
    league_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
    scheduler: LeagueScheduler = Depends(get_league_scheduler),
) -> LeagueDetail:
    """Solo el creador puede iniciarla. Cambia el estado a started y genera el fixture."""
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session, scheduler).start_league(league_id, club)


@router.get(
    "/leagues/{league_id}/matches",
    responses={
        200: {"model": List[Match], "description": "Partidos de la liga"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga aún no fue iniciada"},
    },
    tags=["Leagues"],
    summary="Listar partidos de una liga",
    response_model_by_alias=True,
)
async def list_league_matches(
    league_id: UUID = Path(..., description=""),
    status: Optional[str] = Query(None, description="", alias="status"),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
) -> List[Match]:
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0]().list_league_matches(league_id, status)


@router.get(
    "/leagues/{league_id}/standings",
    responses={
        200: {
            "model": List[StandingsItem],
            "description": "Tabla de posiciones de la liga",
        },
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        404: {"model": Error, "description": "Recurso no encontrado"},
        409: {"model": Error, "description": "La liga aún no fue iniciada"},
    },
    tags=["Leagues"],
    summary="Tabla de posiciones",
    response_model_by_alias=True,
)
async def get_standings(
    league_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    session: AsyncSession = Depends(get_session),
) -> List[StandingsItem]:
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).get_standings(league_id)


@router.get(
    "/leagues/{league_id}/lineup",
    responses={
        200: {"model": SubmitLineupInput, "description": "Alineación vigente"},
        401: {
            "model": Error,
            "description": "No se proporcionó un token, o el token es inválido o expiró",
        },
        403: {"model": Error, "description": "El club no está inscripto en la liga"},
        404: {"model": Error, "description": "Recurso no encontrado"},
    },
    tags=["Leagues"],
    summary="Ver mi alineación en la liga",
    response_model_by_alias=True,
)
async def get_league_lineup(
    league_id: UUID = Path(..., description=""),
    token_bearerAuth: TokenModel = Security(get_token_bearerAuth),
    club: ClubDB = Security(get_current_club),
    session: AsyncSession = Depends(get_session),
) -> SubmitLineupInput:
    if not BaseLeaguesApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseLeaguesApi.subclasses[0](session).get_league_lineup(
        league_id, club
    )