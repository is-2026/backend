import logging

from app.engine.actions import Action
from app.engine.behavior_exec import (
    PlayerBrain,
    compile_behavior,
    create_brains,
    decide_actions,
)
from app.engine.state import MatchState
from app.engine.validation import InvalidBehaviorCode

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

        try:
            compiled_code = compile_behavior(code, player.id)
        except InvalidBehaviorCode:
            logger.exception("El comportamiento del jugador %s no compila", player.id)
            return  # si no compila que quede con el brain viejo
        brain = PlayerBrain(player, compiled_code)
        self._brains[player.id] = brain

    def close(self):
        """Es para ticket ING-172, ahora no hago nada"""
