import pytest

from app.ws.match.pauses import Pause, pauses_schedule


@pytest.mark.parametrize(
    "total_ticks, cb_1_expected, halftime_expected, cb_2_expected",
    [(3000, 750, 1500, 2250), (10, 2, 5, 7), (600, 150, 300, 450)],
)
def test_calculate_pause_schedule(
    total_ticks, cb_1_expected, cb_2_expected, halftime_expected
):
    result = pauses_schedule(total_ticks)

    assert result == {
        cb_1_expected: Pause.COOLING_BREAK_1,
        halftime_expected: Pause.HALFTIME,
        cb_2_expected: Pause.COOLING_BREAK_2,
    }

    assert list(result.values()) == [
        Pause.COOLING_BREAK_1,
        Pause.HALFTIME,
        Pause.COOLING_BREAK_2,
    ]
