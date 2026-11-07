import logging

from app.engine.actions import Action
from app.engine.behavior_exec import (
    create_brains,
    decide_actions,
    load_brain,
)
from app.engine.state import MatchState

logger = logging.getLogger(__name__)


class BehaviorExecutor:
    def __init__(self, state: MatchState, codes: dict[str, str]):
        self._state = state
        self._brains = create_brains(state, codes)

    async def decide(self, state: MatchState) -> dict[str, Action]:
        return decide_actions(state, self._brains)

    def set_behavior(self, player_id: str, code: str):
        player = next(
            (player for player in self._state.players if player.id == player_id), None
        )
        if player is None:
            logger.warning("No existe el jugador %s", player_id)
            return
        brain = load_brain(player, code)
        # si no compila que quede con el brain viejo
        if brain is not None:
            self._brains[player.id] = brain

    def close(self):
        """Es para ticket ING-172, ahora no hago nada"""
