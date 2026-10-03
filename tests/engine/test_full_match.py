import logging

from app.engine.behavior_exec import create_brains, decide_actions
from app.engine.constants import FIELD_HALF_LENGTH, FIELD_HALF_WIDTH
from app.engine.engine import kickoff, step
from tests.engine.test_behavior_exec import same_code_for_all

ATTACKER = """
    def decide_action():
        if has_ball():
            shoot_arco()
        else:
            x, y = my_pos()
            bx, by = ball_pos()
            move(bx - x, by - y, 100)
"""


def play(state, brains, rng, ticks):
    """Juega los ticks como lo haría el runner"""
    goals = []
    for _ in range(ticks):
        actions = decide_actions(state, brains)
        goals += (step(state, actions, rng))
    return goals


def test_full_match_runs_with_behaviors(state, rng, caplog):
    kickoff(state)
    brains = create_brains(state, same_code_for_all(state, ATTACKER))

    goals = play(state, brains, rng, ticks=600)  # 1 minuto

    assert state.tick == 600
    # ningún comportamiento falló
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    # todos siguen dentro de la cancha
    for p in state.players:
        assert abs(p.x) <= FIELD_HALF_LENGTH
        assert abs(p.y) <= FIELD_HALF_WIDTH
    # los dos equipos hacen goles
    home_goals = [g for g in goals if g.team_id == state.home_team_id]
    away_goals = [g for g in goals if g.team_id == state.away_team_id]
    assert home_goals and away_goals
    assert (state.home_score, state.away_score) == (len(home_goals), len(away_goals))
