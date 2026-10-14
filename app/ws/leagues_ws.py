import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.session import SessionLocal
from app.repositories.league_repository import LeagueRepository
from app.ws.auth import authenticate
from app.ws.close_codes import NOT_FOUND
from app.ws.lobby_league import league_lobby_connection

router = APIRouter()


@router.websocket("/ws/leagues/{league_id}/lobby")
async def league_lobby(
                        ws: WebSocket,
                        league_id : uuid.UUID,
                        token : str | None = None
                        ) -> None:
    await ws.accept() #acepto la conexion

    user_id = await authenticate(ws, token) #valido el token, si falla authenticate cierra el ws con 4401
    if user_id is None: #si fallo authenticate retorna None
        return 

    async with SessionLocal() as session: #necesito si o si abrir la sesion, porque al ws no se le inyecta una 
        #sesion como a los endpoints que implementamos
        league = await LeagueRepository(session).get(league_id) #buscamos la liga

    if league is None or league.status != "not_started":
        await ws.close(code = NOT_FOUND) #Cierro el ws (4404)
        return


    league_lobby_connection.connect(league_id,ws) #esto lo que hace es como anotar al cliente en un diccionario, para dejar registrado
    #tal cliente, esta mirando tal loby de tal liga. 
    try:
        while True:
            #Esto lo hago solo para enterarme cuando se desconecta el cliente
            await ws.receive_text()
    except WebSocketDisconnect:
        pass #Simplemente se desconecta el WebSocket xq se fue el cliente, no es nada malo
    finally:
        league_lobby_connection.disconnect(league_id, ws)
