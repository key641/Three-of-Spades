from __future__ import annotations

import re
from typing import Any


_CLOCK_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:：]([0-5]\d)(?!\d)")
_CHINESE_CLOCK_RE = re.compile(
    r"(上午|下午|晚上|傍晚|凌晨|中午)?\s*([0-2]?\d)\s*(?:点|时)(?:\s*(半|[0-5]?\d)\s*分?)?"
)


def normalize_clock_time(value: Any) -> str | None:
    """Normalize model/user time variants to the planner's HH:MM contract."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # ISO datetimes contain date numbers before the clock. Select the final
    # valid clock match instead of letting route parsers read the year as hour.
    matches = list(_CLOCK_RE.finditer(text))
    if matches:
        selected = matches[-1]
        raw_hour, minute = selected.groups()
        period_match = re.search(r"(上午|下午|晚上|傍晚|凌晨|中午)\s*$", text[:selected.start()])
        hour = _apply_period(int(raw_hour), period_match.group(1) if period_match else None)
        return f"{hour:02d}:{int(minute):02d}"

    match = _CHINESE_CLOCK_RE.search(text)
    if not match:
        return None
    period, raw_hour, raw_minute = match.groups()
    hour = int(raw_hour)
    minute = 30 if raw_minute == "半" else int(raw_minute or 0)
    if hour > 23:
        return None
    hour = _apply_period(hour, period)
    return f"{hour:02d}:{minute:02d}"


def _apply_period(hour: int, period: str | None) -> int:
    if period in {"下午", "晚上", "傍晚"} and hour < 12:
        return hour + 12
    if period == "中午" and hour < 11:
        return hour + 12
    if period == "凌晨" and hour == 12:
        return 0
    return hour
