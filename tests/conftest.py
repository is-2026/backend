import pytest

from app.engine.constants import TRIANGLE_HOME
from app.engine.state import MatchState, Side
from app.ws.match.messages import ClubSummary, LineupPlayer, MatchInfo
from tests.engine.conftest import make_player


@pytest.fixture
def match_state():
    """Estado con los 6 jugadores en posiciones distintas y la pelota fuera del centro."""
    players = [
        make_player("h1", Side.HOME, -4, 0),
        make_player("h2", Side.HOME, -12, -5),
        make_player("h3", Side.HOME, -12, 5),
        make_player("a1", Side.AWAY, 4, 0),
        make_player("a2", Side.AWAY, 12, 5),
        make_player("a3", Side.AWAY, 12, -5),
    ]
    state = MatchState(
        home_team_id="club-local",
        home_formation=TRIANGLE_HOME,
        away_team_id="club-visitante",
        away_formation=TRIANGLE_HOME,
        players=players,
        total_ticks=3000,
    )
    state.ball.x = 3.5
    state.ball.y = -1.25
    return state


def lineup_player(player_id, number, is_starter):
    behavior = {"behavior_id": f"b-{player_id}", "behavior_name": "Atacante"} if is_starter else {}
    return LineupPlayer(
        player_id=player_id, number=number, name=f"Jugador {player_id}", is_starter=is_starter,
        power=60, agility=60, control=60, speed=60, strength=60, **behavior,
    )


@pytest.fixture
def match_info():
    """Clubes y alineaciones que corresponden a match_state (titulares h1..h3 y a1..a3)."""
    return MatchInfo(
        home_club=ClubSummary(id="club-local", name="Local", avatar_url="https://x/local.png"),
        away_club=ClubSummary(id="club-visitante", name="Visita", avatar_url="https://x/visita.png"),
        home_lineup=[lineup_player(f"h{n}", n, n <= 3) for n in range(1, 7)],
        away_lineup=[lineup_player(f"a{n}", n, n <= 3) for n in range(1, 7)],
    )
