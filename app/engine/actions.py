"""Acciones que el motor sabe aplicar"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    dx: float
    dy: float
    speed_pct: float


@dataclass(frozen=True)
class Shoot:
    dx: float
    dy: float
    power_pct: float


@dataclass(frozen=True)
class ShootAtGoal:
    pass


@dataclass(frozen=True)
class PassTo:
    target_id: str


Action = Move | Shoot | ShootAtGoal | PassTo
