import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.auth import authenticate
from app.ws.close_codes import NORMAL, NOT_FOUND
from app.ws.match.runner import live_matches, match_connections, started_payload

router = APIRouter()


@router.websocket("/ws/matches/{match_id}")
async def match_stream(
    websocket: WebSocket, match_id: uuid.UUID, token: str | None = None
):
    await websocket.accept()
    if await authenticate(websocket, token) is None:
        return

    live = live_matches.get(match_id)
    if live is None:
        await websocket.close(code=NOT_FOUND)
        return

    try:
        # primero matchStarted y el último estado, y después anotarlo así no le llega un tick viejo después de uno nuevo
        await match_connections.send(websocket, started_payload(live))
        await match_connections.send(websocket, live.last_state)
        if live.current_pause is not None:
            await match_connections.send(websocket, live.current_pause)

        if match_id not in live_matches:
            # terminó mientras le mandábamos el estado: ya nadie lo va a cerrar
            await websocket.close(code=NORMAL)
            return
        match_connections.connect(match_id, websocket)
        while True:
            await (
                websocket.receive_text()
            )  # no esperamos mensajes, solo detectamos la desconexión
    except WebSocketDisconnect:
        pass
    finally:
        match_connections.disconnect(match_id, websocket)
