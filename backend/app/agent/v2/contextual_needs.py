from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeWindow:
    label: str
    start_minutes: int
    end_minutes: int
    core_minutes: int


class ContextualNeedEngine:
    """Derive time-based needs from a normalized trip window.

    A need becomes required only when the itinerary spans the useful core of
    the service window. Touching the edge of a window is not enough to make a
    route infeasible.
    """

    MEAL_WINDOWS = (
        TimeWindow("午餐", 11 * 60 + 30, 13 * 60 + 30, 12 * 60 + 30),
        TimeWindow("晚餐", 17 * 60 + 30, 20 * 60, 18 * 60 + 45),
    )

    def required_meal_windows(self, start_minutes: int, duration_minutes: int) -> list[str]:
        end_minutes = start_minutes + max(0, duration_minutes)
        return [
            window.label
            for window in self.MEAL_WINDOWS
            if start_minutes <= window.core_minutes <= end_minutes
            and min(end_minutes, window.end_minutes) - max(start_minutes, window.start_minutes) >= 60
        ]
