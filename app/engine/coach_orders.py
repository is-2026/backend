from dataclasses import dataclass

@dataclass(frozen=True) #el frozen es para que los objetos de la dataclass sean inmutables (1 vez creados no se pueden cambiar)
class SetBehavior:
    player_id: str
    behavior_id: str

@dataclass(frozen=True)
class Substitute:
    player_out_id: str
    player_in_id: str
    behavior_id: str

@dataclass(frozen=True)
class PenaltyOrder:
    # (player_id, behavior_id) de cada pateador, en el orden en que patean
    kickers: tuple[tuple[str, str], ...]

CoachOrder = SetBehavior | Substitute | PenaltyOrder
