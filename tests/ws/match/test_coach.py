import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.engine.coach_orders import PenaltyOrder, SetBehavior, Substitute
from app.engine.state import Side
from app.ws.match.coach import (
    ClubBehavior,
    CoachSetup,
    apply_coach_orders,
    apply_penalty_orders,
    coach_snapshot,
)
from app.ws.match.pauses import Pause
from app.ws.match.runner import LiveMatch

HOME = "club-local"
AWAY = "club-visitante"

SETUP = CoachSetup(
    code="def decide_coach():\n    pass\n",
    behaviors={"b-def": ClubBehavior(name="Defensor", code="codigo defensor")},
)


@pytest.fixture
def live(match_state, match_info):
    # el executor es un Mock para no levantar procesos, solo el local tiene DT
    return LiveMatch(
        match_id=uuid.uuid4(),
        state=match_state,
        executor=Mock(),
        info=match_info,
        match_start=datetime.now(timezone.utc),
        coaches={HOME: SETUP},
    )


def test_coach_snapshot(live):
    live.state.home_score, live.state.away_score = 2, 1

    snapshot = coach_snapshot(live, HOME)

    assert (snapshot.own_score, snapshot.rival_score) == (2, 1)
    assert snapshot.on_field == (("h1", "b-h1"), ("h2", "b-h2"), ("h3", "b-h3"))
    assert snapshot.bench == ("h4", "h5", "h6")
    assert snapshot.behaviors == (("b-def", "Defensor"),)


def test_set_behavior(live):
    messages = apply_coach_orders(live, {Side.HOME: [SetBehavior("h1", "b-def")]})

    live.executor.set_behavior.assert_called_once_with("h1", "codigo defensor")
    assert live.info.home_lineup[0].behavior_id == "b-def"
    assert messages[0]["type"] == "behaviorChanged"
    assert messages[0]["data"]["player_id"] == "h1"


@pytest.mark.parametrize(
    "order",
    [
        SetBehavior("h1", "b-otro"),  # no es del club
        SetBehavior("a1", "b-def"),  # es del rival
    ],
)
def test_invalid_set_behavior_is_ignored(live, order):
    assert apply_coach_orders(live, {Side.HOME: [order]}) == []
    live.executor.set_behavior.assert_not_called()


def test_substitute_is_scheduled(live):
    apply_coach_orders(live, {Side.HOME: [Substitute("h1", "h4", "b-def")]})

    sub = live.pending_substitutions[HOME]
    assert (sub.player_out_id, sub.player_in_id) == ("h1", "h4")
    assert sub.window == Pause.COOLING_BREAK_1


def test_invalid_substitute_is_ignored(live):
    # h2 no esta en el banco
    apply_coach_orders(live, {Side.HOME: [Substitute("h1", "h2", "b-def")]})

    assert live.pending_substitutions == {}


def test_orders_of_club_without_coach_are_ignored(live):
    assert apply_coach_orders(live, {Side.AWAY: [SetBehavior("a1", "b-def")]}) == []
    live.executor.set_behavior.assert_not_called()


def test_penalty_order(live):
    order = PenaltyOrder(tuple((p, "b-def") for p in ["h4", "h1", "h2", "h3", "h5"]))

    apply_penalty_orders(live, {Side.HOME: [order]})

    kickers = live.penalty_orders[HOME]
    assert [k.id for k in kickers] == ["h4", "h1", "h2", "h3", "h5"]
    assert live.executor.set_player_behavior.call_count == 5


def test_invalid_penalty_order_is_ignored(live):
    # h1 repetido
    kickers = [(p, "b-def") for p in ["h1", "h1", "h2", "h3", "h4"]]

    apply_penalty_orders(live, {Side.HOME: [PenaltyOrder(tuple(kickers))]})

    assert live.penalty_orders == {}
    live.executor.set_player_behavior.assert_not_called()
