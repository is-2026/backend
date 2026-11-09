# coding: utf-8

from sqlalchemy.ext.asyncio import AsyncSession

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from app.apis.ranking_api_base import BaseRankingApi
import app.impl
from app.db.session import get_session

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

from typing import List
from app.models.error import Error
from app.models.ranking_item import RankingItem
from app.models.extra_models import TokenModel  # noqa: F401
from app.security_api import get_token_bearerAuth

router = APIRouter()

ns_pkg = app.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/ranking",
    responses={
        200: {"model": List[RankingItem], "description": "Ranking mundial"},
        401: {"model": Error, "description": "No se proporcionó un token, o el token es inválido o expiró"},
    },
    tags=["Ranking"],
    summary="Ver ranking global",
    response_model_by_alias=True,
)
async def get_ranking(
    token_bearerAuth: TokenModel = Security(
        get_token_bearerAuth
    ), session: AsyncSession = Depends(get_session)
) -> List[RankingItem]:
    """Calculado a partir de los partidos jugados en ligas públicas en curso o terminadas."""
    if not BaseRankingApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseRankingApi.subclasses[0](session).get_ranking()
