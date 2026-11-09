import asyncio
from itertools import groupby
import logging
import uuid

from app.db.session import SessionLocal
from app.repositories.league_repository import LeagueRepository
from app.repositories.match_repository import MatchRepository
from app.ws.close_codes import NORMAL
from app.ws.connection_manager import ConnectionManager
from app.ws.lobby_league import league_lobby_connection
from app.ws.match.starter import MatchStarter, match_starter

logger = logging.getLogger(__name__)

ROUND_WINDOW_SECONDS = 30


class LeagueScheduler:
    """Ejecuta las fechas de una liga iniciada en secuencia."""

    def __init__(
        self,
        session_factory=SessionLocal,
        starter: MatchStarter = match_starter,
        lobby: ConnectionManager = league_lobby_connection,
        window_seconds: float = ROUND_WINDOW_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._starter = starter
        self._lobby = lobby
        self._window_seconds = window_seconds
        self._tasks: set[asyncio.Task] = set()

    # llama al runner de la liga y mantiene la referencia de la task
    def schedule(self, league_id: uuid.UUID) -> asyncio.Task:
        task = asyncio.create_task(self._run_league(league_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _notify_updated(self, league_id: uuid.UUID) -> None:
        await self._lobby.broadcast(
            league_id,
            {"type": "leagueUpdated", "data": {"league_id": str(league_id)}},
        )

    async def _wait_and_notify(
        self, league_id: uuid.UUID, task: asyncio.Task
    ) -> None:
        await task
        await self._notify_updated(league_id)

    async def _run_league(self, league_id: uuid.UUID) -> None:
        # obtiene los partidos de la liga y agrupa por fecha
        try:
            async with self._session_factory() as session:
                matches = await MatchRepository(session).list_by_league(league_id)

            rounds = [
                [m.id for m in group]
                for _, group in groupby(matches, key=lambda m: m.round_number)
            ]
            # corre en simultaneo todos los partidos (por fecha)
            for match_ids in rounds:
                #comenzo nueva fecha (mando leagueUpdated)
                await self._notify_updated(league_id)
                await asyncio.sleep(self._window_seconds)  # la ventana de 30s
                tasks = []
                for match_id in match_ids:
                    #comenzo partido (mando leagueUpdated)
                    task = await self._starter.start(match_id)
                    if task is not None:
                        await self._notify_updated(league_id)
                        #termino partido (mando leagueUpdated)
                        tasks.append(self._wait_and_notify(league_id, task))
                # espera a que se devuelvan todas las tasks (que terminen los partidos) y pasa la siguiente fecha
                if tasks:
                    await asyncio.gather(*tasks)

            # llamo a finish_league para persistir los datos
            async with self._session_factory() as session:
                await LeagueRepository(session).finish_league(league_id)
            # luego broadcast de leagueFinished
            await self._lobby.broadcast(
                league_id,
                {"type": "leagueFinished", "data": {"league_id": str(league_id)}},
            )
        except Exception:
            logger.exception("Falló la ejecución de la liga %s", league_id)
        finally:
            # en cualquier caso, cierro todas las conexiones con 1000
            await self._lobby.close_all(league_id, code=NORMAL)


league_scheduler = LeagueScheduler()
