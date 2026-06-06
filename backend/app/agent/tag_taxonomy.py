from dataclasses import dataclass, field


INTEREST_ALIASES: dict[str, list[str]] = {
    "美食": ["美食", "吃好", "好吃", "好吃的", "餐厅", "吃饭", "小吃", "本帮菜"],
    "咖啡": ["咖啡", "下午茶", "咖啡馆", "咖啡店"],
    "拍照": ["拍照", "出片", "打卡", "网红", "网红打卡"],
    "citywalk": ["citywalk", "城市漫步", "街区", "散步", "逛逛", "城市观光"],
    "艺术展": ["艺术展", "艺术", "展览", "美术馆", "博物馆"],
    "自然风景": ["自然", "风景", "自然风景", "公园", "江景", "海边", "湖边", "山", "森林"],
    "本地感": ["本地感", "本地", "市井", "地道", "老字号"],
    "夜景": ["夜景", "夜游", "晚上", "今晚"],
    "亲子": ["亲子", "亲子友好", "带娃", "小孩", "儿童"],
    "室内": ["室内", "雨天", "下雨"],
    "安静": ["安静", "清净", "人少"],
}

OPTIMIZATION_ALIASES: dict[str, list[str]] = {
    "少排队": ["少排队", "别排队", "不排队", "不想排队", "排队少", "等待时间短"],
    "省钱": ["省钱", "便宜", "便宜点", "更省钱", "预算低"],
    "少走路": ["少走路", "少步行", "步行少", "不走路"],
    "高性价比": ["高性价比", "性价比"],
    "轻松": ["轻松", "不累", "别太累", "不要太累", "慢游"],
    "时间紧": ["时间紧", "赶时间", "快速", "短时间"],
}

AVOID_ALIASES: dict[str, list[str]] = {
    "人流密集": ["人多", "拥挤", "太挤", "人流密集"],
    "排队久": ["排队久", "排队太久"],
    "太贵": ["太贵", "贵", "高价", "消费贵"],
    "需要预约": ["需要预约", "预约", "预约困难", "booking_required"],
    "商业街": ["商业街", "商业化", "商业区"],
    "拍照打卡": ["拍照打卡", "网红打卡"],
    "步行多": ["步行多", "走路多", "太累"],
    "辣": ["辣", "太辣"],
}

NON_PREFERENCE_TERMS = {"一日游", "一天", "半日游", "半天", "day_trip", "替代方案"}
NEGATION_PREFIXES = ("不想", "不要", "不用", "不需要", "别", "避开", "拒绝", "不")


@dataclass
class TagLayers:
    interest_tags: list[str] = field(default_factory=list)
    optimization_goals: list[str] = field(default_factory=list)
    avoid_tags: list[str] = field(default_factory=list)
    unknown_preferences: list[str] = field(default_factory=list)


def split_preference_terms(values: list[str]) -> TagLayers:
    layers = TagLayers()
    for value in values:
        term = str(value).strip()
        if not term or term in NON_PREFERENCE_TERMS:
            continue
        normalized = normalize_interest_tags([term])
        if normalized:
            _extend_unique(layers.interest_tags, normalized)
            continue
        goals = normalize_optimization_goals([term])
        if goals:
            _extend_unique(layers.optimization_goals, goals)
            continue
        avoids = normalize_avoid_tags([term])
        if avoids:
            _extend_unique(layers.avoid_tags, avoids)
            continue
        _append_unique(layers.unknown_preferences, term)
    return layers


def extract_tag_layers(
    message: str = "",
    seed_preferences: list[str] | None = None,
    seed_avoid_tags: list[str] | None = None,
) -> TagLayers:
    layers = split_preference_terms(seed_preferences or [])
    _extend_unique(layers.avoid_tags, normalize_avoid_tags(seed_avoid_tags or []))

    text = message.strip()
    if not text:
        return layers

    for tag, aliases in INTEREST_ALIASES.items():
        if _has_positive_alias(text, aliases):
            _append_unique(layers.interest_tags, tag)
        if _has_negated_alias(text, aliases):
            if tag == "拍照":
                _append_unique(layers.avoid_tags, "拍照打卡")
            elif tag == "美食":
                _remove_value(layers.interest_tags, "美食")
                _remove_value(layers.unknown_preferences, "吃好")

    for goal, aliases in OPTIMIZATION_ALIASES.items():
        if any(alias in text for alias in aliases):
            _append_unique(layers.optimization_goals, goal)

    if any(term in text for term in ["别排队", "不排队", "不想排队", "排队太久", "排队久"]):
        _append_unique(layers.optimization_goals, "少排队")
        _append_unique(layers.avoid_tags, "排队久")
    if any(term in text for term in ["不要太贵", "不想太贵", "别太贵", "太贵"]):
        _append_unique(layers.optimization_goals, "省钱")
        _append_unique(layers.avoid_tags, "太贵")
    if any(term in text for term in ["不要太累", "别太累", "太累", "走路多", "步行多"]):
        _append_unique(layers.optimization_goals, "少走路")
        _append_unique(layers.optimization_goals, "轻松")
        _append_unique(layers.avoid_tags, "步行多")

    for avoid_tag, aliases in AVOID_ALIASES.items():
        if any(alias in text for alias in aliases):
            _append_unique(layers.avoid_tags, avoid_tag)

    return layers


def normalize_interest_tags(values: list[str]) -> list[str]:
    return _normalize_by_alias(values, INTEREST_ALIASES)


def normalize_optimization_goals(values: list[str]) -> list[str]:
    return _normalize_by_alias(values, OPTIMIZATION_ALIASES)


def normalize_avoid_tags(values: list[str]) -> list[str]:
    exact_values = ["排队久" if str(value).strip() == "排队" else str(value).strip() for value in values]
    return _normalize_by_alias(exact_values, AVOID_ALIASES)


def legacy_preferences_from_layers(
    interest_tags: list[str],
    optimization_goals: list[str],
    unknown_preferences: list[str] | None = None,
) -> list[str]:
    return _unique([*interest_tags, *optimization_goals, *(unknown_preferences or [])])


def all_interest_and_goal_terms(values: list[str]) -> list[str]:
    layers = split_preference_terms(values)
    return legacy_preferences_from_layers(layers.interest_tags, layers.optimization_goals, layers.unknown_preferences)


def _normalize_by_alias(values: list[str], aliases: dict[str, list[str]]) -> list[str]:
    result: list[str] = []
    for value in values:
        term = str(value).strip()
        if not term or term in NON_PREFERENCE_TERMS:
            continue
        matched = False
        for canonical, alias_values in aliases.items():
            if term == canonical or term in alias_values:
                _append_unique(result, canonical)
                matched = True
                break
        if not matched and term in aliases:
            _append_unique(result, term)
    return result


def _has_positive_alias(text: str, aliases: list[str]) -> bool:
    return any(alias in text and not _has_negated_alias(text, [alias]) for alias in aliases)


def _has_negated_alias(text: str, aliases: list[str]) -> bool:
    for alias in aliases:
        index = text.find(alias)
        if index < 0:
            continue
        window = text[max(0, index - 5): index]
        for prefix in NEGATION_PREFIXES:
            prefix_index = window.rfind(prefix)
            if prefix_index < 0:
                continue
            between = window[prefix_index + len(prefix):]
            if not any(delimiter in between for delimiter in ("，", ",", "。", "；", ";", "、", " ")):
                return True
    return False


def _remove_value(values: list[str], value: str) -> None:
    while value in values:
        values.remove(value)


def _extend_unique(values: list[str], added: list[str]) -> None:
    for value in added:
        _append_unique(values, value)


def _append_unique(values: list[str], value: str) -> None:
    normalized = str(value).strip()
    if normalized and normalized not in values:
        values.append(normalized)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result
