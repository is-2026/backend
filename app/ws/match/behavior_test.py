import uuid

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.engine.constants import TICKS_PER_MINUTE, TRIANGLE_HOME
from app.engine.state import MatchState, PlayerState, Side
from app.ws.match.info import ClubSummary, LineupPlayer, MatchInfo
from app.ws.match.runner import LiveMatch, start_match, stop_match


def _search_code() -> str:
    return next(b.code for b in DEFAULT_BEHAVIORS if b.name == "Marcador")


def _test_player(side: Side) -> PlayerState:
    return PlayerState(
        id=str(uuid.uuid4()),
        side=side,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
    )


def build_test_state(code: str) -> tuple[MatchState, dict[str, str]]:
    home = _test_player(Side.HOME)
    away = _test_player(Side.AWAY)
    state = MatchState(
        home_team_id=str(uuid.uuid4()),
        home_formation=TRIANGLE_HOME,
        away_team_id=str(uuid.uuid4()),
        away_formation=TRIANGLE_HOME,
        players=[home, away],
        total_ticks=TICKS_PER_MINUTE,  # 600 TICKS
    )
    codes = {home.id: code, away.id: _search_code()}
    return state, codes


def _lineup_player(player: PlayerState, name: str) -> LineupPlayer:
    return LineupPlayer(
        player_id=player.id,
        number=1,
        name=name,
        is_starter=True,
        power=player.power,
        agility=player.agility,
        control=player.control,
        speed=player.speed,
        strength=player.strength,
        behavior_name=name,
    )


def build_test_info(state: MatchState) -> MatchInfo:
    home = state.players[0]
    away = state.players[1]
    return MatchInfo(
        home_club=ClubSummary(id=state.home_team_id, name="Prueba", avatar_url=""),
        away_club=ClubSummary(id=state.away_team_id, name="Marcador", avatar_url=""),
        home_lineup=[_lineup_player(home, "Prueba")],
        away_lineup=[_lineup_player(away, "Marcador")],
    )


behavior_tests: dict[
    uuid.UUID, LiveMatch
] = {}  # el registro que tiene cada club para su prueba (vive en memoria)


def _forget(club_id: uuid.UUID, live: LiveMatch) -> None:
    """Saca la prueba del registro cuando termina, solo si sigue siendo la activa del club."""
    # cuando hacemos una prueba nueva, la vieja se tiene que cortar.
    if behavior_tests.get(club_id) is live:
        behavior_tests.pop(club_id)  # borro la clave de club_id con su valor


async def start_behavior_test(club_id: uuid.UUID, code: str) -> uuid.UUID:
    """Arranca una prueba 1 vs 1 sin pausas y corta la anterior del mismo club."""
    
    test_run = behavior_tests.get(club_id)  #se fija si hay una prueba corriendo

    state, codes = build_test_state(code) ## armo el partido
    info = build_test_info(state)
    match_id = uuid.uuid4()
    live = start_match(match_id, state, codes, info, pauses=False )

    behavior_tests[club_id] = live  #Registro la prueba como la activa del club
    live.task.add_done_callback(lambda _: _forget(club_id, live)) # cuando termina la prueba llama a _forget

    if test_run is not None:   ## Si hay una prueba vieja, la corto
        await stop_match(test_run)
    return match_id
