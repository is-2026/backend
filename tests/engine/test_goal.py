import pytest

from app.engine.constants import TRIANGLE_HOME
from app.engine.engine import step


@pytest.mark.parametrize(
    "x, vx, last_touch, expected_team, expected_home, expected_away",
    [
        # gol del local en el arco de la derecha
        (19.5, 10.0, "h1", "club-local", 1, 0),
        # gol del visitante en el arco de la izquierda
        (-19.5, -10.0, "a1", "club-visitante", 0, 1),
        # gol en contra en el arco de la derecha
        (19.5, 10.0, "a1", "club-local", 1, 0),
    ],
)
def test_goal(
    state, rng, x, vx, last_touch, expected_team, expected_home, expected_away
):
    ball = state.ball
    ball.x, ball.y, ball.vx, ball.vy = x, 0.0, vx, 0.0
    ball.last_touch_id = last_touch

    events = step(state, {}, rng)

    assert len(events) == 1
    assert events[0].team_id == expected_team
    assert events[0].player_id == last_touch
    assert (state.home_score, state.away_score) == (expected_home, expected_away)
    # después del gol, todo vuelve a la posición inicial
    assert (ball.x, ball.y, ball.vx, ball.vy) == (0.0, 0.0, 0.0, 0.0)
    assert (state.players[0].x, state.players[0].y) == TRIANGLE_HOME[0]


def test_ball_hits_outside_the_post_is_not_goal(state, rng):
    ball = state.ball
    ball.x, ball.y, ball.vx = 19.5, 2.0, 10.0  # el arco llega hasta y = 1.5

    events = step(state, {}, rng)

    assert events == []
    assert (state.home_score, state.away_score) == (0, 0)
    assert ball.vx < 0  # rebotó
