from app.agent.schemas import SessionState
from app.agent.message_router import MessageRoute, TurnType
from app.schemas.intent import Intent


ADJUSTMENT_TERMS = [
    "预算低",
    "便宜",
    "省钱",
    "别排队",
    "少排队",
    "不排队",
    "不想排队",
    "少走路",
    "不要太累",
    "别太累",
    "轻松",
    "换一家",
    "换个",
    "换成",
    "换到",
    "改成",
    "改一下",
    "刚刚",
    "刚刚的方案",
    "方案",
    "不要这个",
    "太贵",
    "太远",
    "打车",
    "开车",
    "不走路",
    "再",
    "继续",
    "更",
    "一点",
    "一些",
]


def is_adjustment_message(message: str) -> bool:
    return any(term in message for term in ADJUSTMENT_TERMS)


def apply_session_context(intent: Intent, message: str, state: SessionState, route: MessageRoute | None = None) -> Intent:
    should_inherit = bool(
        state.last_intent
        and (
            is_adjustment_message(message)
            or route
            and route.inherit_previous
        )
    )
    if not should_inherit:
        return intent

    base = state.last_intent.model_dump()
    current = intent.model_dump()
    merged = base | {
        "preferences": _unique([*state.last_intent.preferences, *intent.preferences]),
        "avoid_tags": _unique([*state.last_intent.avoid_tags, *intent.avoid_tags]),
        "need_clarification": False,
    }

    if intent.city_from_message:
        merged["city"] = intent.city
        merged["city_from_message"] = True

    is_add_constraint = bool(route and route.turn_type == TurnType.ADD_CONSTRAINT)
    if not is_add_constraint:
        for key in ("budget_per_person", "people_count", "start_time", "duration_hours"):
            if current.get(key) != Intent().model_dump().get(key):
                merged[key] = current[key]

    preserve_scenario = bool(is_add_constraint and route and route.preserve_scenario)
    if not preserve_scenario and current.get("scenario") != Intent().model_dump().get("scenario"):
        merged["scenario"] = current["scenario"]

    return Intent.model_validate(merged)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result
