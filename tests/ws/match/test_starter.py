import uuid

import pytest

from app.db.match import MatchDB
from app.db.player import PlayerDB
from app.engine.constants import FRIENDLY_TOTAL_TICKS
from app.engine.engine import kickoff
from app.engine.state import Side
from app.repositories.friendly_repository import StarterData
from app.ws.match.starter import InvalidLineup, build_match_state


def make_starter(club_id, number, code="def decide_action(): pass"):
    player = PlayerDB(
        id=uuid.uuid4(), name=f"J{number}", number=number,
        power=60, agility=60, control=60, speed=60, strength=60, club_id=club_id,
    )
    return StarterData(club_id=club_id, player=player, code=code)


@pytest.fixture
def match():
    return MatchDB(id=uuid.uuid4(), home_club_id=uuid.uuid4(), away_club_id=uuid.uuid4())


@pytest.fixture
def starters(match):
    home = [make_starter(match.home_club_id, n, f"home{n}") for n in (1, 2, 3)]
    away = [make_starter(match.away_club_id, n, f"away{n}") for n in (1, 2, 3)]
    return away + home  # mezclados a propósito


def test_build_match_state_splits_sides(match, starters):
    state, _ = build_match_state(match, starters)

    assert state.home_team_id == str(match.home_club_id)
    assert state.away_team_id == str(match.away_club_id)
    assert [p.side for p in state.players] == [Side.HOME] * 3 + [Side.AWAY] * 3
    assert state.total_ticks == FRIENDLY_TOTAL_TICKS == 3000


def test_build_match_state_codes_by_player_id(match, starters):
    _, codes = build_match_state(match, starters)

    assert codes == {str(s.player.id): s.code for s in starters}


def test_order_decides_formation_position(match, starters):
    state, _ = build_match_state(match, starters)
    kickoff(state)

    first_home = state.players[0]
    first_away = state.players[3]
    assert first_home.id == str(starters[3].player.id)
    assert (first_home.x, first_home.y) == (-4.0, 0.0)
    assert (first_away.x, first_away.y) == (4.0, 0.0)


def test_missing_starter_raises(match, starters):
    with pytest.raises(InvalidLineup):
        build_match_state(match, starters[1:])
