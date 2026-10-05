import pytest

from app.engine.constants import TRIANGLE_HOME
from app.engine.state import MatchState, Side
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
