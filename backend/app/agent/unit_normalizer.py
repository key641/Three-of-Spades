import math
import re

from app.agent.schemas import IntentDelta


CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def normalize_delta_units(delta: IntentDelta, message: str) -> IntentDelta:
    """Normalize explicit natural-language units into schema standard units."""

    data = delta.model_dump()
    explicit_fields = extract_standard_unit_fields(message)
    if explicit_fields:
        data["modified_hard_constraints"] = {
            **data["modified_hard_constraints"],
            **explicit_fields,
        }
    return IntentDelta.model_validate(data)


def extract_standard_unit_fields(message: str) -> dict[str, object]:
    text = message.strip()
    fields: dict[str, object] = {}

    people_count = _extract_people_count(text)
    if people_count is not None:
        fields["people_count"] = people_count

    duration_hours = _extract_duration_hours(text)
    if duration_hours is not None:
        fields["duration_hours"] = duration_hours

    start_time = _extract_start_time(text)
    if start_time is not None:
        fields["start_time"] = start_time

    budget = _extract_budget_per_person(text, people_count)
    if budget is not None:
        fields["budget_per_person"] = budget

    return fields


def _extract_duration_hours(text: str) -> int | None:
    if any(term in text for term in ["一日游", "一天", "1天"]):
        return 8
    if any(term in text for term in ["半日游", "半天"]):
        return 4

    day_match = re.search(r"(\d+)\s*天", text)
    if day_match:
        return max(1, int(day_match.group(1))) * 8

    chinese_day_match = re.search(r"([一二两三四五六七八九十])\s*天", text)
    if chinese_day_match:
        return CHINESE_NUMBERS[chinese_day_match.group(1)] * 8

    minute_match = re.search(r"(\d+)\s*(?:分钟|min|MIN)", text)
    if minute_match:
        before = text[max(0, minute_match.start() - 4) : minute_match.start()]
        if any(term in before for term in ["排队", "等待", "等位", "路上", "交通"]):
            return None
        return max(1, math.ceil(int(minute_match.group(1)) / 60))

    hour_match = re.search(r"(\d+)\s*(?:小时|h|H)", text)
    if hour_match:
        before = text[max(0, hour_match.start() - 4) : hour_match.start()]
        if any(term in before for term in ["排队", "等待", "等位", "路上", "交通"]):
            return None
        return max(1, int(hour_match.group(1)))

    chinese_hour_match = re.search(r"([一二两三四五六七八九十])\s*小时", text)
    if chinese_hour_match:
        return CHINESE_NUMBERS[chinese_hour_match.group(1)]

    return None


def _extract_people_count(text: str) -> int | None:
    if any(term in text for term in ["双人", "两个人", "两人", "2个人", "2人", "我们俩"]):
        return 2
    if any(term in text for term in ["单人", "一个人", "1个人", "1人", "我自己", "独自"]):
        return 1

    digit_match = re.search(r"(\d+)\s*(?:人|个人|位)", text)
    if digit_match:
        return max(1, int(digit_match.group(1)))

    chinese_match = re.search(r"([一二两三四五六七八九十])\s*(?:人|个人|位)", text)
    if chinese_match:
        return CHINESE_NUMBERS[chinese_match.group(1)]

    return None


def _extract_budget_per_person(text: str, people_count: int | None) -> int | None:
    per_person_patterns = [
        r"(?:人均|每人|单人|一个人)\s*(\d+)",
        r"(\d+)\s*(?:元|块)?\s*(?:每人|人均|一人)",
    ]
    for pattern in per_person_patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, int(match.group(1)))

    total_patterns = [
        r"(?:总预算|总共|一共|合计)\s*(\d+)",
        r"(\d+)\s*(?:元|块)?\s*(?:总预算|总共|一共|合计)",
    ]
    for pattern in total_patterns:
        match = re.search(pattern, text)
        if match:
            total_budget = max(1, int(match.group(1)))
            if people_count and people_count > 0:
                return max(1, math.floor(total_budget / people_count))
            return total_budget

    budget_match = re.search(r"(?:预算|以内|不超过|控制在)\s*(\d+)", text)
    if budget_match:
        return max(1, int(budget_match.group(1)))

    return None


def _extract_start_time(text: str) -> str | None:
    clock_match = re.search(r"(\d{1,2})(?::|：)(\d{2})", text)
    if clock_match:
        return _format_time(int(clock_match.group(1)), int(clock_match.group(2)))

    period = _time_period(text)
    digit_hour_match = re.search(r"(\d{1,2})\s*点", text)
    if digit_hour_match and _has_time_of_day_context(text, digit_hour_match.start()):
        return _format_time(_apply_period(int(digit_hour_match.group(1)), period), 0)

    chinese_hour_match = re.search(r"([一二两三四五六七八九十])\s*点", text)
    if chinese_hour_match and _has_time_of_day_context(text, chinese_hour_match.start()):
        hour = CHINESE_NUMBERS[chinese_hour_match.group(1)]
        return _format_time(_apply_period(hour, period), 0)

    if any(term in text for term in ["上午", "早上"]):
        return "09:00"
    if "中午" in text:
        return "12:00"
    if "下午" in text:
        return "14:00"
    if any(term in text for term in ["晚上", "今晚"]):
        return "19:00"

    return None


def _has_time_of_day_context(text: str, index: int) -> bool:
    if any(term in text for term in ["上午", "早上", "中午", "下午", "晚上", "今晚"]):
        return True
    nearby = text[max(0, index - 4) : index + 8]
    return any(term in nearby for term in ["出发", "开始", "到达", "集合", "开玩", "过去", "前往"])


def _time_period(text: str) -> str:
    if any(term in text for term in ["下午", "晚上", "今晚"]):
        return "pm"
    if "中午" in text:
        return "noon"
    return "am"


def _apply_period(hour: int, period: str) -> int:
    if period == "pm" and hour < 12:
        return hour + 12
    if period == "noon" and hour < 11:
        return hour + 12
    return hour


def _format_time(hour: int, minute: int) -> str:
    return f"{hour % 24:02d}:{minute:02d}"
