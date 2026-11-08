import pytest

from app.ws.match.live_behavior import (
    PlayerNotOnField,
    update_info_match,
    validate_player_on_field,
)
from app.ws.match.substitutions import ClubNotInMatch

# match_state y match_info vienen de tests/ws/match/conftest.py:
# en cancha h1..h3 (local) y a1..a3 (visitante); en el banco h4..h6 y a4..a6.
# Los titulares arrancan con behavior_id "b-<id>" y behavior_name "Atacante".


def _lineup_player(lineup, player_id):
    return next(p for p in lineup if p.player_id == player_id)


@pytest.mark.parametrize(
    "team_id, player_id", [("club-local", "h1"), ("club-visitante", "a1")]
)
def test_validate_player_on_field(team_id, player_id, match_state, match_info):
    result = validate_player_on_field(match_state, match_info, team_id, player_id)

    assert result is None


def test_validate_player_on_the_bench(match_state, match_info):
    with pytest.raises(PlayerNotOnField):
        validate_player_on_field(match_state, match_info, "club-local", "h4")


def test_validate_player_of_the_rival(match_state, match_info):
    # a1 está en cancha pero es del otro club
    with pytest.raises(PlayerNotOnField):
        validate_player_on_field(match_state, match_info, "club-local", "a1")


def test_validate_player_that_does_not_exist(match_state, match_info):
    with pytest.raises(PlayerNotOnField):
        validate_player_on_field(match_state, match_info, "club-local", "nadie")


def test_validate_player_club_not_in_match(match_state, match_info):
    # get_side tira antes de mirar al jugador
    with pytest.raises(ClubNotInMatch):
        validate_player_on_field(match_state, match_info, "cualquiera", "h1")


def test_update_info_match_home(match_info):
    update_info_match(match_info, "club-local", "h1", "behavior-nuevo", "Defensor")

    player = _lineup_player(match_info.home_lineup, "h1")
    assert player.behavior_id == "behavior-nuevo"
    assert player.behavior_name == "Defensor"


def test_update_info_match_away(match_info):
    update_info_match(match_info, "club-visitante", "a2", "behavior-nuevo", "Defensor")

    player = _lineup_player(match_info.away_lineup, "a2")
    assert player.behavior_id == "behavior-nuevo"
    assert player.behavior_name == "Defensor"
