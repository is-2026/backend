import uuid
 
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
 
from app.db.session import SessionLocal
from app.repositories.friendly_repository import FriendlyRepository
from app.ws.auth import authenticate
from app.ws.close_codes import NOT_FOUND
from app.ws.lobby_friendly import friendly_start_times, lobby_connection

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

    rival_club_id = friendly.rival_club_id
    rival_name = None
    if rival_club_id is not None:
        rival_name = await repo.get_club_name(rival_club_id)


    lobby_connection.connect(friendly_id, ws)
    try:
        if rival_club_id is not None: # el rival ya se unió antes de que este cliente se conectara: se lo avisamos igual
            starts_at = friendly_start_times.get(friendly_id)
            try:
                await lobby_connection.send(ws, {
                    "type": "friendlyClubRegistered",
                    "data": {
                            "friendly_id": str(friendly_id),
                            "club_id": str(rival_club_id),
                            "club_name": rival_name,
                            "starts_at": starts_at.isoformat() if starts_at else None,
                    },
                })
            except Exception:
                pass  # si el cliente no responde, el loop de abajo detecta que se fue

        while True:
            await ws.receive_text()  # solo para enterarnos cuando el cliente se va
    except WebSocketDisconnect:
        pass
    finally:
        lobby_connection.disconnect(friendly_id, ws)