import random

import pytest

from app.engine.constants import TRIANGLE_HOME
from app.engine.state import MatchState, PlayerState, Side


def make_player(
    id: str, side: Side, x: float = 0.0, y: float = 0.0, **pacss: int
) -> PlayerState:
    """Jugador con atributos por defecto en 60. La suma total SIEMPRE debe ser 300."""

    attrs = {"power": 60, "agility": 60, "control": 60, "speed": 60, "strength": 60}

    for key, value in pacss.items():
        if key in attrs:
            attrs[key] = value
        else:
            raise ValueError(f"El atributo '{key}' es inválido.")

    total_sum = sum(attrs.values())

    if total_sum != 300:
        raise ValueError(
            f"El jugador {id} es inválido: los atributos suman {total_sum}, "
            f"pero deben sumar exactamente 300."
        )

    return PlayerState(id=id, side=side, x=x, y=y, **attrs)


@pytest.fixture
def rng():
    return random.Random(42)  # semilla fija: los tests son reproducibles


@pytest.fixture
def state():
    players = [
        make_player("h1", Side.HOME, -4, 0),
        make_player("h2", Side.HOME, -12, -5),
        make_player("h3", Side.HOME, -12, 5),
        make_player("a1", Side.AWAY, 4, 0),
        make_player("a2", Side.AWAY, 12, 5),
        make_player("a3", Side.AWAY, 12, -5),
    ]
    return MatchState(
        home_team_id="club-local",
        home_formation=TRIANGLE_HOME,
        away_team_id="club-visitante",
        away_formation=TRIANGLE_HOME,
        players=players,
        total_ticks=3000,
    )
