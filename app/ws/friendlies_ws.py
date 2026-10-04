import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.session import SessionLocal
from app.repositories.friendly_repository import FriendlyRepository
from app.ws.auth import authenticate
from app.ws.close_codes import NOT_FOUND
from app.ws.lobby_friendly import lobby_connection

router = APIRouter()


@router.websocket("/ws/friendlies/{friendly_id}/lobby")
async def friendly_lobby(
    ws: WebSocket, friendly_id: uuid.UUID, token: str | None = None
) -> None:
    await ws.accept()  # Acepto la conexion para poder cerrar con algun codigo

    user_id = await authenticate(ws, token)  # si es inválido ya cerró con 4401
    if user_id is None:
        return

    async with SessionLocal() as session: #abro una session corta para la consulta
        friendly = await FriendlyRepository(session).get(friendly_id)
    if friendly is None:
        await ws.close(code=NOT_FOUND)
        return

    lobby_connection.connect(friendly_id, ws)
    try:
        while True:
            await ws.receive_text()  # solo para enterarnos cuando el cliente se va
    except WebSocketDisconnect:
        pass
    finally:
        lobby_connection.disconnect(friendly_id, ws)