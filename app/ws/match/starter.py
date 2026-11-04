import asyncio
import logging
import uuid

from app.db.club import ClubDB
from app.db.match import MatchDB, MatchStatus
from app.db.session import SessionLocal
from app.engine.constants import FRIENDLY_TOTAL_TICKS, TRIANGLE_HOME
from app.engine.state import MatchState, PlayerState, Side
from app.repositories.club_repository import ClubRepository
from app.repositories.friendly_repository import FriendlyRepository, SquadMember
from app.repositories.match_repository import MatchRepository
from app.ws.match.info import ClubSummary, LineupPlayer, MatchInfo
from app.ws.match.runner import LiveMatch, live_matches, start_match

logger = logging.getLogger(__name__)

STARTERS_PER_TEAM = 3


class InvalidLineup(Exception):
    """Algun club no tiene exactamente 3 titulares con comportamiento."""


def _player_state(member: SquadMember, side: Side) -> PlayerState:
    p = member.player
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
    match: MatchDB, squad: list[SquadMember]
) -> tuple[MatchState, dict[str, str]]:
    """Arma el estado inicial del motor y codes = player_id -> código.
    Solo entran los titulares; su orden en `squad` decide la posición en la formación."""
    starters = [m for m in squad if m.is_starter and m.behavior is not None]
    home = [m for m in starters if m.club_id == match.home_club_id]
    away = [m for m in starters if m.club_id == match.away_club_id]
    if len(home) != STARTERS_PER_TEAM or len(away) != STARTERS_PER_TEAM:
        raise InvalidLineup(
            f"Partido {match.id}: {len(home)} titulares local, {len(away)} visitante"
        )

    state = MatchState(
        home_team_id=str(match.home_club_id),
        home_formation=TRIANGLE_HOME,
        away_team_id=str(match.away_club_id),
        away_formation=TRIANGLE_HOME,  # el motor lo espeja
        players=[_player_state(m, Side.HOME) for m in home]
        + [_player_state(m, Side.AWAY) for m in away],
        total_ticks=FRIENDLY_TOTAL_TICKS,
    )
    codes = {str(m.player.id): m.behavior.code for m in starters}
    return state, codes


def _club_summary(club: ClubDB) -> ClubSummary:
    return ClubSummary(id=str(club.id), name=club.club_name, avatar_url=club.avatar_url)


def _lineup_player(member: SquadMember) -> LineupPlayer:
    p, b = member.player, member.behavior
    return LineupPlayer(
        player_id=str(p.id),
        number=p.number,
        name=p.name,
        is_starter=member.is_starter,
        power=p.power,
        agility=p.agility,
        control=p.control,
        speed=p.speed,
        strength=p.strength,
        behavior_id=str(b.id) if b else None,
        behavior_name=b.name if b else None,
    )


def build_match_info(
    home_club: ClubDB, away_club: ClubDB, squad: list[SquadMember]
) -> MatchInfo:
    """Lo que va en matchStarted: clubes y los 6 convocados de cada uno."""
    return MatchInfo(
        home_club=_club_summary(home_club),
        away_club=_club_summary(away_club),
        home_lineup=[_lineup_player(m) for m in squad if m.club_id == home_club.id],
        away_lineup=[_lineup_player(m) for m in squad if m.club_id == away_club.id],
    )


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
            clubs = ClubRepository(session)
            home_club = await clubs.get_by_id(match.home_club_id)
            away_club = await clubs.get_by_id(match.away_club_id)
            squad = await FriendlyRepository(session).get_squad_by_match(match_id)

            state, codes = build_match_state(match, squad)
            info = build_match_info(home_club, away_club, squad)

            live = start_match(match_id, state, codes, info)
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
