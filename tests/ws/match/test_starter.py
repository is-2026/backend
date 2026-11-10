import uuid

import pytest

from app.db.behavior import BehaviorDB
from app.db.club import ClubDB
from app.db.match import MatchDB
from app.db.player import PlayerDB
from app.engine.constants import FORMATIONS, FRIENDLY_TOTAL_TICKS
from app.engine.engine import kickoff
from app.engine.state import Side
from app.repositories.friendly_repository import SquadMember
from app.ws.match.coach import ClubBehavior
from app.ws.match.starter import (
    InvalidLineup,
    build_coach_setup,
    build_match_info,
    build_match_state,
)


def make_member(club_id, number, is_starter):
    player = PlayerDB(
        id=uuid.uuid4(), name=f"J{number}", number=number,
        power=60, agility=60, control=60, speed=60, strength=60, club_id=club_id,
    )
    behavior = (
        BehaviorDB(id=uuid.uuid4(), name=f"B{number}", code=f"code{number}", club_id=club_id)
        if is_starter else None
    )
    return SquadMember(club_id=club_id, player=player, is_starter=is_starter, behavior=behavior)


def make_squad(club_id):
    """Titulares 1, 2, 3 (con comportamiento) y suplentes 4, 5, 6."""
    return [make_member(club_id, n, n <= 3) for n in range(1, 7)]


@pytest.fixture
def home_club():
    return ClubDB(id=uuid.uuid4(), club_name="Local", avatar_url="https://x/local.png")


@pytest.fixture
def away_club():
    return ClubDB(id=uuid.uuid4(), club_name="Visita", avatar_url="https://x/visita.png")


@pytest.fixture
def match(home_club, away_club):
    return MatchDB(id=uuid.uuid4(), home_club_id=home_club.id, away_club_id=away_club.id)


@pytest.fixture
def squad(home_club, away_club):
    return make_squad(away_club.id) + make_squad(home_club.id)  # visitante primero a propósito


def test_build_match_state_only_starters_split_by_side(match, squad):
    state, _ = build_match_state(match, squad)

    assert state.home_team_id == str(match.home_club_id)
    assert state.away_team_id == str(match.away_club_id)
    assert [p.side for p in state.players] == [Side.HOME] * 3 + [Side.AWAY] * 3
    starters = {str(m.player.id) for m in squad if m.is_starter}
    assert {p.id for p in state.players} == starters
    assert state.total_ticks == FRIENDLY_TOTAL_TICKS == 3000


def test_build_match_state_codes_by_player_id(match, squad):
    _, codes = build_match_state(match, squad)

    assert codes == {str(m.player.id): m.behavior.code for m in squad if m.is_starter}


def test_order_decides_formation_position(match, squad):
    state, _ = build_match_state(match, squad)
    kickoff(state)

    first_home = state.players[0]
    first_away = state.players[3]
    assert first_home.id == str(squad[6].player.id)  # el primer titular del local
    assert (first_home.x, first_home.y) == (-4.0, 0.0)
    assert (first_away.x, first_away.y) == (4.0, 0.0)


@pytest.mark.parametrize("formation", FORMATIONS)
def test_starters_take_their_formation(match, squad, formation):
    state, _ = build_match_state(
        match, squad, home_formation=formation, away_formation=formation
    )
    kickoff(state)

    home = [(p.x, p.y) for p in state.players if p.side == Side.HOME]
    away = [(p.x, p.y) for p in state.players if p.side == Side.AWAY]
    assert home == list(FORMATIONS[formation])
    assert away == [(-x, -y) for x, y in FORMATIONS[formation]]  # espejado


def test_each_club_can_have_its_own_formation(match, squad):
    state, _ = build_match_state(
        match, squad, home_formation="OFFENSIVE_LINE", away_formation="DEFENSIVE_LINE"
    )

    assert state.home_formation == FORMATIONS["OFFENSIVE_LINE"]
    assert state.away_formation == FORMATIONS["DEFENSIVE_LINE"]


def test_missing_starter_raises(match, squad):
    with pytest.raises(InvalidLineup):
        build_match_state(match, squad[1:])


def test_starter_without_behavior_raises(match, squad):
    squad[0] = squad[0]._replace(behavior=None)
    with pytest.raises(InvalidLineup):
        build_match_state(match, squad)


def test_build_match_info(home_club, away_club, squad):
    info = build_match_info(home_club, away_club, squad)

    assert info.home_club.model_dump() == {
        "id": str(home_club.id), "name": "Local", "avatar_url": "https://x/local.png",
    }
    assert info.away_club.name == "Visita"
    assert [p.number for p in info.home_lineup] == [1, 2, 3, 4, 5, 6]
    assert [p.player_id for p in info.away_lineup] == [str(m.player.id) for m in squad[:6]]

    starter, sub = info.home_lineup[0], info.home_lineup[3]
    assert starter.is_starter and starter.behavior_name == "B1"
    assert starter.behavior_id == str(squad[6].behavior.id)
    assert not sub.is_starter and sub.behavior_id is None


# --- DT ---


def test_build_coach_setup(home_club):
    coach = BehaviorDB(id=uuid.uuid4(), name="DT", code="dt", kind="coach")
    player = BehaviorDB(id=uuid.uuid4(), name="Ata", code="ata", kind="player")
    home_club.coach_behavior_id = coach.id

    setup = build_coach_setup(home_club, [coach, player])

    assert setup.code == "dt"
    # solo los de jugador
    assert setup.behaviors == {str(player.id): ClubBehavior(name="Ata", code="ata")}
