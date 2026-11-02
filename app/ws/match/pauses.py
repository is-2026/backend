from enum import StrEnum

# Segundos totales de las pausas, no avanzan los ticks
COOLING_BREAK_SECONDS = 15
HALFTIME_SECONDS = 15


class Pause(StrEnum):
    COOLING_BREAK_1 = "cooling_break_1"
    HALFTIME = "halftime"
    COOLING_BREAK_2 = "cooling_break_2"


def pauses_schedule(total_ticks: int) -> dict[int, Pause]:
    return {
        total_ticks // 4: Pause.COOLING_BREAK_1,
        total_ticks // 2: Pause.HALFTIME,
        3 * total_ticks // 4: Pause.COOLING_BREAK_2,
    }
