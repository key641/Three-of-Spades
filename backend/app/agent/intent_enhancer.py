import re

from app.schemas.intent import Intent


CITY_ALIASES: dict[str, list[str]] = {
    "北京": ["北京", "帝都"],
    "上海": ["上海", "魔都"],
    "广州": ["广州"],
    "深圳": ["深圳"],
    "成都": ["成都"],
    "杭州": ["杭州"],
    "南京": ["南京"],
    "武汉": ["武汉"],
    "西安": ["西安"],
    "苏州": ["苏州"],
    "重庆": ["重庆"],
}

PREFERENCE_ALIASES: dict[str, list[str]] = {
    "少排队": ["少排队", "别排队", "不排队", "不想排队", "排队少"],
    "吃好": ["吃好", "美食", "好吃", "好吃的", "餐厅", "吃饭", "小吃"],
    "更省钱": ["省钱", "便宜", "性价比", "高性价比", "预算低"],
    "少走路": ["少走路", "别太累", "不要太累", "轻松", "不累"],
    "citywalk": ["citywalk", "城市漫步", "街区", "散步", "逛逛"],
    "拍照": ["拍照", "出片", "打卡", "网红"],
    "亲子友好": ["亲子", "带娃", "小孩", "儿童"],
    "室内": ["室内", "雨天", "下雨"],
    "安静": ["安静", "清净", "人少"],
}

PREFERENCE_CANONICAL_ALIASES: dict[str, str] = {
    alias: normalized
    for normalized, aliases in PREFERENCE_ALIASES.items()
    for alias in aliases
}

NEGATIVE_PREFERENCE_ALIASES: dict[str, list[str]] = {
    "吃好": ["不要吃饭", "不吃饭", "不用吃饭", "别吃饭", "不要餐厅", "不安排吃饭", "不用安排吃饭"],
}

AVOID_ALIASES: dict[str, list[str]] = {
    "人流密集": ["人多", "拥挤", "太挤", "人流密集"],
    "排队久": ["排队久", "排队太久", "别排队", "不排队", "不想排队"],
    "太贵": ["太贵", "贵", "高价", "消费贵"],
    "商业街": ["商业街", "商业化"],
    "辣": ["辣", "太辣"],
    "步行多": ["步行多", "走路多", "太累", "少走路", "别太累", "不要太累"],
}

AVOID_CANONICAL_ALIASES: dict[str, str] = {
    alias: normalized
    for normalized, aliases in AVOID_ALIASES.items()
    for alias in aliases
}

START_TIME_HINTS: dict[str, str] = {
    "上午": "09:00",
    "早上": "09:00",
    "下午": "14:00",
    "晚上": "19:00",
    "今晚": "19:00",
}

NON_PREFERENCE_TERMS = {"一日游", "一天", "半日游", "半天", "day_trip"}


def enhance_intent_from_message(intent: Intent, message: str) -> Intent:
    text = message.strip()
    data = intent.model_dump()

    city = _extract_city(text)
    if city:
        data["city"] = city
        data["city_from_message"] = True

    people_count = _extract_people_count(text)
    if people_count:
        data["people_count"] = people_count

    duration_hours = _extract_duration_hours(text)
    if duration_hours:
        data["duration_hours"] = duration_hours

    budget = _extract_budget(text)
    if budget:
        data["budget_per_person"] = budget

    start_time = _extract_start_time(text)
    if start_time:
        data["start_time"] = start_time

    added_preferences = _extract_terms(text, PREFERENCE_ALIASES)
    removed_preferences = _extract_terms(text, NEGATIVE_PREFERENCE_ALIASES)
    data["preferences"] = _remove_values(
        _remove_non_preferences(_unique([*_normalize_preferences(intent.preferences), *added_preferences])),
        removed_preferences,
    )
    data["avoid_tags"] = _unique([*_normalize_avoid_tags(intent.avoid_tags), *_extract_terms(text, AVOID_ALIASES)])

    if city or duration_hours or data["preferences"] or data["avoid_tags"]:
        data["need_clarification"] = False

    if "亲子友好" in data["preferences"]:
        data["scenario"] = "family_trip"
    elif "吃好" in data["preferences"]:
        data["scenario"] = "foodie_tour"
    elif "citywalk" in data["preferences"]:
        data["scenario"] = "friends_citywalk"

    return Intent.model_validate(data)


def extract_explicit_trip_fields(message: str) -> dict[str, object]:
    text = message.strip()
    fields: dict[str, object] = {}
    city = _extract_city(text)
    if city:
        fields["city"] = city
    people_count = _extract_people_count(text)
    if people_count:
        fields["people_count"] = people_count
    duration_hours = _extract_duration_hours(text)
    if duration_hours:
        fields["duration_hours"] = duration_hours
    budget = _extract_budget(text)
    if budget:
        fields["budget_per_person"] = budget
    start_time = _extract_start_time(text)
    if start_time:
        fields["start_time"] = start_time
    return fields


def extract_removed_preferences(message: str) -> list[str]:
    return _extract_terms(message.strip(), NEGATIVE_PREFERENCE_ALIASES)


def normalize_preferences(values: list[str]) -> list[str]:
    return _unique(_normalize_preferences(values))


def normalize_avoid_tags(values: list[str]) -> list[str]:
    return _unique(_normalize_avoid_tags(values))


def _extract_city(text: str) -> str | None:
    for city, aliases in CITY_ALIASES.items():
        if any(alias in text for alias in aliases):
            return city
    return None


def _extract_people_count(text: str) -> int | None:
    if any(term in text for term in ["双人", "两个人", "2个人", "2人", "有朋友和我一起", "朋友和我一起", "朋友跟我一起"]):
        return 2
    if any(term in text for term in ["单人", "一个人", "1个人", "1人", "我自己", "独自"]):
        return 1

    match = re.search(r"(\d+)\s*(?:人|个人|位)", text)
    if match:
        return int(match.group(1))

    chinese_numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    match = re.search(r"([一二两三四五六七八九十])\s*(?:人|个人|位)", text)
    if match:
        return chinese_numbers[match.group(1)]
    return None


def _extract_duration_hours(text: str) -> int | None:
    if any(term in text for term in ["一日游", "一天", "1天"]):
        return 8
    if any(term in text for term in ["半日游", "半天"]):
        return 4

    day_match = re.search(r"(\d+)\s*天", text)
    if day_match:
        return max(1, int(day_match.group(1))) * 8

    hour_match = re.search(r"(\d+)\s*(?:小时|h|H)", text)
    if hour_match:
        return max(1, int(hour_match.group(1)))
    return None


def _extract_budget(text: str) -> int | None:
    patterns = [
        r"(?:人均|每人|预算|以内|不超过|低于)\s*(\d+)\s*(?:元|块)?",
        r"(\d+)\s*(?:元|块)\s*(?:以内|以下|左右)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _extract_start_time(text: str) -> str | None:
    clock_match = re.search(r"(\d{1,2})(?::|：)(\d{2})", text)
    if clock_match:
        return f"{int(clock_match.group(1)):02d}:{int(clock_match.group(2)):02d}"

    hour_match = re.search(r"(\d{1,2})\s*点", text)
    if hour_match:
        return f"{int(hour_match.group(1)):02d}:00"

    for hint, value in START_TIME_HINTS.items():
        if hint in text:
            return value
    return None


def _extract_terms(text: str, aliases: dict[str, list[str]]) -> list[str]:
    terms: list[str] = []
    for normalized, values in aliases.items():
        if any(value in text for value in values):
            terms.append(normalized)
    return terms


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _remove_non_preferences(values: list[str]) -> list[str]:
    return [value for value in values if value not in NON_PREFERENCE_TERMS]


def _normalize_preferences(values: list[str]) -> list[str]:
    return [PREFERENCE_CANONICAL_ALIASES.get(value, value) for value in values]


def _normalize_avoid_tags(values: list[str]) -> list[str]:
    return [AVOID_CANONICAL_ALIASES.get(value, value) for value in values]


def _remove_values(values: list[str], removed_values: list[str]) -> list[str]:
    removed = set(removed_values)
    return [value for value in values if value not in removed]
