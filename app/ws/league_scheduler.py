import asyncio
from itertools import groupby
import logging
import uuid

from app.db.session import SessionLocal
from app.repositories.league_repository import LeagueRepository
from app.repositories.match_repository import MatchRepository
from app.ws.match.starter import MatchStarter, match_starter

logger = logging.getLogger(__name__)

ROUND_WINDOW_SECONDS = 30


class LeagueScheduler:
    """Ejecuta las fechas de una liga iniciada en secuencia."""

    def __init__(
        self,
        session_factory=SessionLocal,
        starter: MatchStarter = match_starter,
        window_seconds: float = ROUND_WINDOW_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._starter = starter
        self._window_seconds = window_seconds
        self._tasks: set[asyncio.Task] = set()

    # llama al runner de la liga y mantiene la referencia de la task
    def schedule(self, league_id: uuid.UUID) -> asyncio.Task:
        task = asyncio.create_task(self._run_league(league_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

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
                await asyncio.sleep(self._window_seconds)   #la ventana de 30s
                tasks = [
                    task
                    for match_id in match_ids
                    if (task := await self._starter.start(match_id)) is not None
                ]
                # espera a que se devuelvan todas las tasks (que terminen los partidos) y pasa la siguiente fecha
                if tasks:
                    await asyncio.gather(*tasks)
            # llamo a finish_league para persistir los datos
            async with self._session_factory() as session:
                await LeagueRepository(session).finish_league(league_id)
        except Exception:
            logger.exception("Falló la ejecución de la liga %s", league_id)


league_scheduler = LeagueScheduler()
