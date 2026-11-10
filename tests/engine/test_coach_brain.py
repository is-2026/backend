from textwrap import dedent

import pytest

from app.engine.behavior_exec import CoachSnapshot, load_coach_brain
from app.engine.coach_orders import PenaltyOrder, SetBehavior, Substitute
from app.engine.state import Side

ON_FIELD = (("h1", "b1"), ("h2", "b1"), ("h3", "b2"))
BENCH = ("h4", "h5", "h6")
BEHAVIORS = (("b1", "Atacante"), ("b2", "Defensor"))
KICKERS = [("h1", "b1"), ("h2", "b1"), ("h3", "b1"), ("h4", "b2"), ("h5", "b2")]


@pytest.fixture
def snapshot():
    return CoachSnapshot(
        own_score=2,
        rival_score=1,
        tick=120,
        total_ticks=3000,
        on_field=ON_FIELD,
        bench=BENCH,
        behaviors=BEHAVIORS,
        penalty_shootout=False,
    )


@pytest.fixture
def penalties():
    return CoachSnapshot(
        own_score=2,
        rival_score=1,
        tick=120,
        total_ticks=3000,
        on_field=ON_FIELD,
        bench=BENCH,
        behaviors=BEHAVIORS,
        penalty_shootout=True,
    )


def make_coach(code):
    return load_coach_brain(Side.HOME, dedent(code))


def run_coach(code, snapshot):
    return make_coach(code).run(snapshot)


def test_reading_primitives(snapshot):
    coach = make_coach("def decide_coach():\n    pass\n")
    coach.run(snapshot)

    assert coach.score() == (2, 1)
    assert coach.time() == 120
    assert coach.total_time() == 3000
    assert coach.on_field() == list(ON_FIELD)
    assert coach.bench() == list(BENCH)
    assert coach.behaviors() == list(BEHAVIORS)
    assert coach.is_penalty_shootout() is False


def test_set_behavior(snapshot):
    code = """
        def decide_coach():
            set_behavior("h1", "b2")
    """
    assert run_coach(code, snapshot) == [SetBehavior("h1", "b2")]


def test_set_behavior_first_call_wins(snapshot):
    code = """
        def decide_coach():
            set_behavior("h1", "b2")
            set_behavior("h1", "b1")
    """
    assert run_coach(code, snapshot) == [SetBehavior("h1", "b2")]


def test_set_behavior_same_behavior_does_nothing(snapshot):
    # h1 ya tiene b1
    code = """
        def decide_coach():
            set_behavior("h1", "b1")
    """
    assert run_coach(code, snapshot) == []


def test_only_first_substitute(snapshot):
    code = """
        def decide_coach():
            substitute("h1", "h4", "b2")
            substitute("h2", "h5", "b2")
    """
    assert run_coach(code, snapshot) == [Substitute("h1", "h4", "b2")]


def test_penalties_ignore_set_behavior_and_substitute(penalties):
    code = """
        def decide_coach():
            set_behavior("h1", "b2")
            substitute("h1", "h4", "b2")
    """
    assert run_coach(code, penalties) == []


def test_penalty_order(penalties):
    code = f"""
        def decide_coach():
            penalty_order({KICKERS!r})
    """
    assert run_coach(code, penalties) == [PenaltyOrder(tuple(KICKERS))]


@pytest.mark.parametrize("kickers", ["[('h1', 'b1')] * 4", "['ab'] * 5"])
def test_wrong_penalty_order_is_ignored(penalties, kickers):
    code = f"""
        def decide_coach():
            penalty_order({kickers})
    """
    assert run_coach(code, penalties) == []


def test_exception_discards_orders(snapshot):
    code = """
        def decide_coach():
            set_behavior("h1", "b2")
            1 / 0
    """
    assert run_coach(code, snapshot) == []
