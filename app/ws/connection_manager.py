import asyncio
import uuid

from fastapi import WebSocket

from app.ws.close_codes import NORMAL


class ConnectionManager:
    """Conexiones abiertas por canal (match_id, friendly_id, league_id...).

    No acepta conexiones: eso lo decide cada endpoint, porque antes de registrar
    puede tener que cerrar con 4401/4404. Cada canal usa su propia instancia.
    """

    def __init__(self, send_timeout: float = 1.0) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}
        # máximo que esperamos a un cliente; si no, uno trabado frena a todos
        self._send_timeout = send_timeout

    def connect(self, channel_id: uuid.UUID, websocket: WebSocket) -> None:
        if channel_id not in self._connections:
            self._connections[channel_id] = set()

        self._connections[channel_id].add(websocket)

    def disconnect(self, channel_id: uuid.UUID, websocket: WebSocket) -> None:
        """No falla si ya no estaba. Si el canal queda vacío, se borra la clave."""
        connections = self._connections.get(channel_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            del self._connections[channel_id]

    def is_connected(self, channel_id: uuid.UUID, websocket: WebSocket) -> bool:
        return websocket in self._connections.get(channel_id, set())

    async def send(self, websocket: WebSocket, message: dict) -> None:
        """A un solo cliente, con timeout (ej: el estado al conectarse).
        Si falla o se pasa del tiempo, lanza la excepción: decide quien llama."""
        await asyncio.wait_for(websocket.send_json(message), self._send_timeout)

    async def broadcast(self, channel_id: uuid.UUID, message: dict) -> None:
        """A todos los del canal. Si falla o se pasa del timeout, se lo saca y se sigue."""
        # copia porque _send_or_drop puede sacar conexiones mientras recorremos
        connections = list(self._connections.get(channel_id, set()))
        # en paralelo, un cliente lento no suma su timeout al de los demás
        await asyncio.gather(
            *(self._send_or_drop(channel_id, ws, message) for ws in connections)
        )

    async def close_all(self, channel_id: uuid.UUID, code: int = NORMAL) -> None:
        """Cierra todas las conexiones del canal y lo olvida."""
        for websocket in self._connections.pop(channel_id, set()):
            try:
                await websocket.close(code=code)
            except Exception:
                pass  # el cliente ya se había ido, no hay nada que cerrar

    async def _send_or_drop(
        self, channel_id: uuid.UUID, websocket: WebSocket, message: dict
    ) -> None:
        try:
            await self.send(websocket, message)
        except Exception:
            self.disconnect(channel_id, websocket)
