from textwrap import dedent

import pytest

from app.engine.actions import Move
from app.engine.executor import BehaviorExecutor
from app.engine.state import Side
from app.ws.match.pauses import Pause
from app.ws.match.substitutions import (
    ClubNotInMatch,
    InvalidSubstitution,
    NoPendingSubstitution,
    PendingSubstitution,
    SubstitutionConflict,
    cancel,
    execute_substitution,
    get_side,
    schedule,
    substitution_window,
    validate_players,
)
from tests.engine.conftest import same_code_for_all

GO_RIGHT = """
    def decide_action():
        move(1, 0, 100)
"""

GO_LEFT = """
    def decide_action():
        move(-1, 0, 100)
"""


def pending_sub(player_out_id="h1", player_in_id="h4") -> PendingSubstitution:
    return PendingSubstitution(
        "s1",
        player_out_id,
        player_in_id,
        "b1",
        "bname",
        dedent(GO_RIGHT),
        Pause.HALFTIME,
    )


@pytest.mark.parametrize(
    "in_pause, pauses_started, expected",
    [
        (False, 0, Pause.COOLING_BREAK_1),
        (True, 1, Pause.COOLING_BREAK_1),
        (False, 1, Pause.HALFTIME),
        (True, 2, Pause.HALFTIME),
        (False, 2, Pause.COOLING_BREAK_2),
        (True, 3, Pause.COOLING_BREAK_2),
    ],
)
def test_substitution_window(in_pause, pauses_started, expected):
    assert substitution_window(in_pause, pauses_started) == expected


def test_no_windows_left_after_third_pause():
    with pytest.raises(SubstitutionConflict, match="ventanas"):
        substitution_window(False, 3)


@pytest.mark.parametrize(
    "team_id, side_expected", [("club-local", Side.HOME), ("club-visitante", Side.AWAY)]
)
def test_get_side(team_id, side_expected, match_info):
    assert get_side(team_id, match_info) == side_expected


def test_team_not_in_match(match_info):
    with pytest.raises(ClubNotInMatch):
        get_side("cualquiera", match_info)


def test_validate_players(match_info, match_state):
    validate_players(match_state, match_info, "club-local", "h1", "h4")


@pytest.mark.parametrize(
    "player_out_id, player_in_id",
    [
        ("h4", "h5"),  # el que sale es suplente
        ("a1", "h4"),  # el que sale es del otro equipo
        ("h1", "h2"),  # el que entra ya está en la cancha
        ("h1", "a4"),  # el que entra es del otro equipo
        ("h1", "x9"),  # el que entra no es de ningún equipo
    ],
)
def test_validate_players_invalid(match_info, match_state, player_out_id, player_in_id):
    with pytest.raises(InvalidSubstitution):
        validate_players(
            match_state, match_info, "club-local", player_out_id, player_in_id
        )


def test_schedule():
    pending = {}
    sub_h = pending_sub()
    sub_a = pending_sub("a1", "a4")
    schedule(pending, "club-local", sub_h)

    assert pending == {"club-local": sub_h}

    schedule(pending, "club-visitante", sub_a)

    assert pending == {"club-local": sub_h, "club-visitante": sub_a}


def test_double_schedule_raises_conflict():
    pending = {}
    sub_h = pending_sub()
    schedule(pending, "club-local", sub_h)

    assert pending == {"club-local": sub_h}

    with pytest.raises(SubstitutionConflict, match="programada"):
        sub_h2 = pending_sub("h2", "h6")
        schedule(pending, "club-local", sub_h2)


def test_cancel():
    sub_h = pending_sub()
    pending = {"club-local": sub_h}

    res = cancel(pending, "club-local")

    assert pending == {}
    assert res == sub_h


def test_cancel_without_pending():
    pending = {}

    with pytest.raises(NoPendingSubstitution):
        cancel(pending, "club_local")


@pytest.mark.parametrize(
    "club, out_p, in_p, side, expected_move",
    [
        ("club-local", "h1", "h4", Side.HOME, Move(1.0, 0.0, 100.0)),
        ("club-visitante", "a1", "a4", Side.AWAY, Move(-1.0, 0.0, 100.0)),
    ],
)
async def test_execute_substitution(
    match_state, match_info, club, out_p, in_p, side, expected_move
):
    lineup = match_info.home_lineup if side == Side.HOME else match_info.away_lineup
    lineup[3].power = 80  # [3] es h4 o a4
    lineup[3].speed = 40
    ids_before = [p.id for p in match_state.players]
    executor = BehaviorExecutor(
        match_state, same_code_for_all(match_state, dedent(GO_LEFT))
    )
    sub = pending_sub(out_p, in_p)
    execute_substitution(match_state, match_info, executor, club, sub)

    assert [p.id for p in match_state.players] == [
        in_p if pid == out_p else pid for pid in ids_before
    ]
    player = next(p for p in match_state.players if p.id == in_p)
    assert player.side == side
    assert player.power == 80
    assert player.speed == 40

    actions = await executor.decide(match_state)

    assert actions[in_p] == expected_move
    assert out_p not in actions
