from itertools import combinations
from math import dist

import pytest

from app.engine.constants import (
    FIELD_HALF_WIDTH,
    FORMATIONS,
    SOCIAL_DISTANCING,
)
from app.engine.engine import step
from app.models.formation_preset import FormationPreset


def test_formations_match_the_contract():
    assert set(FORMATIONS) == {f.value for f in FormationPreset}


@pytest.mark.parametrize("name", FORMATIONS)
def test_formation_is_valid(name):
    positions = FORMATIONS[name]

    assert len(positions) == 3
    for x, y in positions:
        assert x < 0  # en la mitad propia
        assert abs(y) <= FIELD_HALF_WIDTH
    for a, b in combinations(positions, 2):
        assert dist(a, b) >= SOCIAL_DISTANCING


def test_after_goal_each_team_goes_back_to_its_formation(state, rng):
    state.home_formation = FORMATIONS["OFFENSIVE_LINE"]
    state.away_formation = FORMATIONS["DEFENSIVE_LINE"]
    state.ball.x, state.ball.vx, state.ball.last_touch_id = 19.5, 10.0, "h1"

    step(state, {}, rng)

    home = [(p.x, p.y) for p in state.players[:3]]
    away = [(p.x, p.y) for p in state.players[3:]]
    assert home == list(FORMATIONS["OFFENSIVE_LINE"])
    assert away == [(-x, -y) for x, y in FORMATIONS["DEFENSIVE_LINE"]]
