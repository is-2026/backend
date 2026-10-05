import uuid

from fastapi import Depends, HTTPException, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.club import ClubDB
from app.db.session import get_session
from app.models.extra_models import TokenModel
from app.repositories.club_repository import ClubRepository
from app.security_api import get_token_bearerAuth
from app.ws.connection_manager import ConnectionManager
from app.ws.lobby_friendly import lobby_connection

async def get_current_club(
    token: TokenModel = Security(get_token_bearerAuth), #get_token_bearerAuth se ejecuta primero, si falla tira error y no llega a la funcion
    session: AsyncSession = Depends(get_session),
) -> ClubDB:
    # sub es el id del usuario (ya validado como UUID en get_token_bearerAuth)
    club = await ClubRepository(session).get_by_user_id(uuid.UUID(token.sub)) #tolken.sub busco el club de ese usuario
    if club is None:
        raise HTTPException(status_code=404, detail="El usuario no tiene un club creado")
    return club

def get_lobby_manager() -> ConnectionManager: #para poder mockear en los tests
    return lobby_connection