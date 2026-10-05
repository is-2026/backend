import asyncio
import logging
import uuid

from app.db.match import MatchDB, MatchStatus
from app.db.session import SessionLocal
from app.engine.constants import FRIENDLY_TOTAL_TICKS, TRIANGLE_HOME
from app.engine.state import MatchState, PlayerState, Side
from app.repositories.friendly_repository import FriendlyRepository, StarterData
from app.repositories.match_repository import MatchRepository
from app.ws.match.runner import LiveMatch, live_matches, start_match

logger = logging.getLogger(__name__)

STARTERS_PER_TEAM = 3


class InvalidLineup(Exception):
    """Algun club no tiene exactamente 3 titulares con comportamiento."""


def _player_state(starter: StarterData, side: Side) -> PlayerState:
    p = starter.player
    return PlayerState(
        id=str(p.id),
        side=side,
        power=p.power,
        agility=p.agility,
        control=p.control,
        speed=p.speed,
        strength=p.strength,
    )


def build_match_state(
    match: MatchDB, starters: list[StarterData]
) -> tuple[MatchState, dict[str, str]]:
    """Arma el estado inicial del motor y codes = player_id -> código.
    El orden de `starters` decide la posición en la formación."""
    home = [s for s in starters if s.club_id == match.home_club_id]
    away = [s for s in starters if s.club_id == match.away_club_id]
    if len(home) != STARTERS_PER_TEAM or len(away) != STARTERS_PER_TEAM:
        raise InvalidLineup(
            f"Partido {match.id}: {len(home)} titulares local, {len(away)} visitante"
        )

    state = MatchState(
        home_team_id=str(match.home_club_id),
        home_formation=TRIANGLE_HOME,
        away_team_id=str(match.away_club_id),
        away_formation=TRIANGLE_HOME,  # el motor lo espeja
        players=[_player_state(s, Side.HOME) for s in home]
        + [_player_state(s, Side.AWAY) for s in away],
        total_ticks=FRIENDLY_TOTAL_TICKS,
    )
    codes = {str(s.player.id): s.code for s in starters}
    return state, codes


class MatchStarter:
    """Carga un partido de la base y lo larga en el runner."""

    def __init__(self, session_factory=SessionLocal) -> None:
        # la sesión del request ya se cerro cuando esto corre: abrimos las nuestras
        self._session_factory = session_factory
        self._tasks: set[asyncio.Task] = set()

    async def start(self, match_id: uuid.UUID) -> None:
        if match_id in live_matches:
            return

        async with self._session_factory() as session:
            match = await MatchRepository(session).get_by_id(match_id)
            if match is None:
                raise LookupError(f"No existe el partido {match_id}")
            starters = await FriendlyRepository(session).get_starters_by_match(match_id)
            state, codes = build_match_state(match, starters)

            live = start_match(match_id, state, codes)
            await MatchRepository(session).set_status(match_id, MatchStatus.in_progress)

        task = asyncio.create_task(self._save_result(live))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _save_result(self, live: LiveMatch) -> None:
        """Espera a que termine el runner y guarda el resultado."""
        await live.task
        try:
            async with self._session_factory() as session:
                await MatchRepository(session).finish(
                    live.match_id, live.state.home_score, live.state.away_score
                )
        except Exception:
            logger.exception("No se pudo guardar el resultado de %s", live.match_id)


match_starter = MatchStarter()