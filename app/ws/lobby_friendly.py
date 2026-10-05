from app.ws.connection_manager import ConnectionManager

# Instancia única: la comparten el endpoint WS y FriendliesApiImpl.
lobby_connection = ConnectionManager()