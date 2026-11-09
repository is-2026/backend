import uuid
from textwrap import dedent

import pytest

from app.engine.actions import Move
from app.ws.match.coach import ClubBehavior, CoachSetup
from app.ws.match.runner import live_matches, match_connections, start_match
from tests.ws.conftest import FakeWebSocket

# pausas despues de los ticks 10, 20 y 30
TOTAL_TICKS = 40

NO_WAIT = {
    "tick_interval": 0,
    "start_delay": 0,
    "cooling_break_duration": 0,
    "halftime_duration": 0,
    "penalty_window": 0,
    "penalty_pause": 0,
}

GO_RIGHT = "def decide_action():\n    move(1, 0, 100)\n"
GO_LEFT = "def decide_action():\n    move(-1, 0, 100)\n"


def coach(code):
    behaviors = {"b-left": ClubBehavior(name="Izquierda", code=GO_LEFT)}
    return {"club-local": CoachSetup(code=dedent(code), behaviors=behaviors)}


@pytest.fixture
def match_id():
    return uuid.uuid4()


@pytest.fixture
def client(match_id):
    ws = FakeWebSocket()
    match_connections.connect(match_id, ws)
    return ws


@pytest.fixture
def play(match_id, match_state, match_info):
    match_state.total_ticks = TOTAL_TICKS
    codes = {p.id: GO_RIGHT for p in match_state.players}
    h1_actions = {}  # tick -> accion de h1

    async def run(coaches, **kwargs):
        live = start_match(
            match_id,
            match_state,
            kwargs.pop("codes", codes),
            match_info,
            coaches=coaches,
            **NO_WAIT,
            **kwargs,
        )
        decide = live.executor.decide_with_coach

        async def save_h1(state, snapshots):
            tick = state.tick
            actions, orders = await decide(state, snapshots)
            h1_actions[tick] = actions.get("h1")
            return actions, orders

        live.executor.decide_with_coach = save_h1
        await live.task
        return live, h1_actions

    yield run
    live_matches.pop(match_id, None)


def sent_of_type(client, message_type):
    return [m for m in client.sent if m["type"] == message_type]


async def test_set_behavior_in_tick_10_changes_from_tick_11(play, client):
    _, h1_actions = await play(
        coach(
            """
            def decide_coach():
                if time() == 10:
                    set_behavior("h1", "b-left")
            """
        )
    )

    assert h1_actions[10] == Move(1.0, 0.0, 100.0)
    assert h1_actions[11] == Move(-1.0, 0.0, 100.0)
    (changed,) = sent_of_type(client, "behaviorChanged")
    assert changed["data"]["tick"] == 11


async def test_substitute_is_done_in_the_next_pause(play, client):
    live, _ = await play(
        coach(
            """
            def decide_coach():
                if time() == 2:
                    substitute("h2", "h4", "b-left")
            """
        )
    )

    (made,) = sent_of_type(client, "substitutionMade")
    assert made["data"]["tick"] == 10
    assert "h4" in [p.id for p in live.state.players]


@pytest.mark.parametrize(
    "code",
    [
        """
        def decide_coach():
            set_behavior("h1", "b-left")
            raise ValueError()
        """,
        """
        def decide_coach():
            set_behavior("h1", "b-left")
            while True:
                pass
        """,
    ],
)
async def test_broken_coach_does_not_change_anything(play, client, code):
    live, h1_actions = await play(coach(code))

    assert live.state.tick == TOTAL_TICKS
    assert client.sent[-1]["type"] == "matchFinished"
    assert sent_of_type(client, "behaviorChanged") == []
    assert set(h1_actions.values()) == {Move(1.0, 0.0, 100.0)}


async def test_coach_chooses_the_penalty_kickers(play, client):
    # nadie se mueve: termina 0 a 0 y va a penales
    live, _ = await play(
        coach(
            """
            def decide_coach():
                if is_penalty_shootout():
                    kickers = ["h4", "h5", "h6", "h1", "h2"]
                    penalty_order([(p, "b-left") for p in kickers])
            """
        ),
        codes={},
        allows_draws=False,
    )

    assert [k.id for k in live.penalty_orders["club-local"]] == [
        "h4",
        "h5",
        "h6",
        "h1",
        "h2",
    ]
    kicks = sent_of_type(client, "penaltyKick")
    home_kickers = [
        k["data"]["kicker_id"] for k in kicks if k["data"]["team_id"] == "club-local"
    ]
    assert home_kickers[:3] == ["h4", "h5", "h6"]
