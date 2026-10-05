import uuid
from datetime import datetime


from app.ws.connection_manager import ConnectionManager

# Instancia única: la comparten el endpoint WS y FriendliesApiImpl.
lobby_connection = ConnectionManager()

friendly_start_times: dict[uuid.UUID, datetime] = {}