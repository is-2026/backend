import uuid

import jwt
from fastapi import WebSocket

from app.security.tokens import get_user_id
from app.ws.close_codes import UNAUTHORIZED


async def authenticate(websocket: WebSocket, token: str | None) -> uuid.UUID | None:
    """Para endpoints WS, después del accept().
    Devuelve el id del usuario, o cierra con 4401 y devuelve None."""
    if token:
        try:
            return get_user_id(token)
        except (jwt.InvalidTokenError, ValueError):
            pass  # token inválido: se cierra igual que si no viniera
    await websocket.close(code=UNAUTHORIZED)
    return None
