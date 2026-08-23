from __future__ import annotations

from app.agent.schemas import IntentDelta, QueryUnderstanding, SessionState, StateChangeSummary, TripState
from app.agent.message_router import MessageRoute, TurnType
from app.agent.intent_enhancer import (
    extract_explicit_trip_fields,
    normalize_avoid_tags,
    normalize_goal_preferences,
    normalize_interest_preferences,
    normalize_preferences,
)
from app.agent.tag_taxonomy import legacy_preferences_from_layers
from app.agent.unit_normalizer import extract_standard_unit_fields
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

    current = intent.model_dump()
    previous = state.last_intent.model_dump()
    default = Intent().model_dump()

    # ---- 核心变更：当前消息为 BASE，上一轮只补缺 ----
    merged = dict(current)

    # 显式字段：从消息原文直接提取的值，优先级最高
    explicit_fields = extract_explicit_trip_fields(message) | extract_standard_unit_fields(message)

    # 硬约束继承规则：
    # 1. explicit_fields 中有 → 用 explicit_fields（消息原文提取，最可靠）
    # 2. 上一轮有 → 继承上一轮
    # 3. 都没有 → 保持当前 LLM 解析值
    hard_keys = (
        "city", "people_count", "target_district", "target_business_area",
        "start_location_name", "start_lat", "start_lng",
        "start_time", "duration_hours", "budget_per_person",
    )
    for key in hard_keys:
        if key in explicit_fields:
            merged[key] = explicit_fields[key]
        elif key in previous:
            merged[key] = previous[key]
        # else: keep current

    # 城市特殊处理：当前消息明确提到了城市 → 用当前的
    if intent.city_from_message:
        merged["city"] = intent.city
        merged["city_from_message"] = True

    # 场景：继承上一轮
    if "scenario" in previous:
        merged["scenario"] = previous["scenario"]

    # 偏好/兴趣处理：
    # - ADD_CONSTRAINT 或 is_adjustment_message（无 route 时的兜底）：UNION 合并
    # - 其他模式且当前有偏好：当前覆盖上一轮
    # - 其他模式且当前无偏好：继承上一轮
    is_add_constraint = bool(route and route.turn_type == TurnType.ADD_CONSTRAINT)
    is_local_edit = _is_local_route_edit(message, route)
    is_merge_mode = is_add_constraint or is_local_edit or (route is None and is_adjustment_message(message))
    has_current_prefs = bool(intent.preferences or intent.interest_tags or intent.optimization_goals)

    if is_merge_mode:
        # 真正追加场景（"还要吃饭"、"预算低一点"）：合并新旧偏好
        merged["interest_tags"] = normalize_interest_preferences([
            *state.last_intent.interest_tags, *state.last_intent.preferences,
            *intent.interest_tags, *intent.preferences,
        ])
        merged["optimization_goals"] = normalize_goal_preferences([
            *state.last_intent.optimization_goals, *state.last_intent.preferences,
            *intent.optimization_goals, *intent.preferences,
        ])
        merged["preferences"] = normalize_preferences([
            *state.last_intent.preferences, *intent.preferences,
        ])
    elif has_current_prefs:
        # 当前消息自带偏好 → 当前覆盖上一轮
        merged["interest_tags"] = normalize_interest_preferences(intent.interest_tags)
        merged["optimization_goals"] = normalize_goal_preferences(intent.optimization_goals)
        merged["preferences"] = normalize_preferences(intent.preferences)
    else:
        # 当前无偏好 → 继承上一轮
        merged["interest_tags"] = normalize_interest_preferences(state.last_intent.interest_tags)
        merged["optimization_goals"] = normalize_goal_preferences(state.last_intent.optimization_goals)
        merged["preferences"] = normalize_preferences(state.last_intent.preferences)

    # avoid_tags 始终合并（否定偏好是累积的）
    merged["avoid_tags"] = normalize_avoid_tags([*state.last_intent.avoid_tags, *intent.avoid_tags])

    merged["need_clarification"] = False
    return Intent.model_validate(merged)


def _is_local_route_edit(message: str, route: MessageRoute | None) -> bool:
    if not route or not route.inherit_previous:
        return False
    local_edit_terms = [
        "换一家",
        "替换",
        "替代",
        "替代方案",
        "等待时间短",
        "排队",
        "当前路线",
        "这条路线",
        "route_",
    ]
    return bool(route.references_previous_route or any(term in message for term in local_edit_terms))


def apply_query_delta(
    intent: Intent,
    state: SessionState,
    understanding: QueryUnderstanding,
    delta: IntentDelta,
) -> tuple[Intent, TripState, StateChangeSummary]:
    base_state = _base_trip_state(intent, state, understanding)
    original = base_state.model_dump()
    data = base_state.model_dump()
    summary = StateChangeSummary()

    _apply_hard_constraint_changes(data, delta, summary)
    added_interest = normalize_interest_preferences(delta.added_preferences)
    removed_interest = normalize_interest_preferences(delta.removed_preferences)
    added_goals = normalize_goal_preferences(delta.added_preferences)
    removed_goals = normalize_goal_preferences(delta.removed_preferences)
    _apply_list_changes(data, "soft_preferences", delta.added_preferences, delta.removed_preferences, summary)
    _apply_list_changes(data, "interest_tags", added_interest, removed_interest, summary)
    _apply_list_changes(data, "optimization_goals", added_goals, removed_goals, summary)
    _apply_list_changes(data, "avoid_tags", delta.added_avoid_tags, delta.removed_avoid_tags, summary)
    promoted_needs = set(delta.added_must_include) & set(delta.removed_implicit_needs)
    visible_removed_implicit_needs = [value for value in delta.removed_implicit_needs if value not in promoted_needs]
    _apply_list_changes(data, "implicit_needs", delta.added_implicit_needs, visible_removed_implicit_needs, summary)
    _apply_list_changes(data, "must_include", delta.added_must_include, delta.removed_must_include, summary)

    for value in delta.added_must_include:
        if value in data["implicit_needs"]:
            data["implicit_needs"] = [item for item in data["implicit_needs"] if item != value]

    if understanding.inherit_previous:
        for key in (
            "city",
            "people_count",
            "target_district",
            "target_business_area",
            "start_location_name",
            "start_lat",
            "start_lng",
            "start_time",
            "duration_hours",
            "budget_per_person",
            "scenario",
        ):
            if key not in summary.changed:
                summary.kept.append(key)

    data["hard_constraints"] = {
        "city": data["city"],
        "people_count": data["people_count"],
        "target_district": data["target_district"],
        "target_business_area": data["target_business_area"],
        "start_location_name": data["start_location_name"],
        "start_lat": data["start_lat"],
        "start_lng": data["start_lng"],
        "start_time": data["start_time"],
        "duration_hours": data["duration_hours"],
        "budget_per_person": data["budget_per_person"],
    }
    removed_legacy_preferences = set(normalize_preferences(delta.removed_preferences))
    kept_soft_preferences = [value for value in data["soft_preferences"] if value not in removed_legacy_preferences]
    data["soft_preferences"] = _unique([
        *legacy_preferences_from_layers(data["interest_tags"], data["optimization_goals"]),
        *kept_soft_preferences,
    ])

    trip_state = TripState.model_validate(data)
    merged_intent = trip_state.to_intent()
    merged_intent.city_from_message = bool(
        intent.city_from_message
        or original.get("city") != trip_state.city
        or "city" in delta.modified_hard_constraints
        or "city" in delta.added_hard_constraints
    )
    return merged_intent, trip_state, summary


def _base_trip_state(intent: Intent, state: SessionState, understanding: QueryUnderstanding) -> TripState:
    if understanding.inherit_previous:
        if state.trip_state:
            return state.trip_state
        if state.last_intent:
            return TripState.from_intent(state.last_intent)
    return TripState.from_intent(intent)


def _apply_hard_constraint_changes(data: dict, delta: IntentDelta, summary: StateChangeSummary) -> None:
    for key in delta.removed_hard_constraints:
        if key in data["hard_constraints"]:
            _append_unique(summary.removed, key)
            data["hard_constraints"].pop(key, None)

    changes = delta.added_hard_constraints | delta.modified_hard_constraints
    for key, value in changes.items():
        if key not in {
            "city",
            "people_count",
            "target_district",
            "target_business_area",
            "start_location_name",
            "start_lat",
            "start_lng",
            "start_time",
            "duration_hours",
            "budget_per_person",
            "scenario",
        }:
            data["hard_constraints"][key] = value
            continue
        previous = data.get(key)
        if previous != value:
            data[key] = value
            if key == "start_location_name":
                data["start_lat"] = None
                data["start_lng"] = None
            summary.changed[key] = {"from": previous, "to": value}


def _apply_list_changes(
    data: dict,
    field: str,
    added_values: list[str],
    removed_values: list[str],
    summary: StateChangeSummary,
) -> None:
    current = list(data[field])
    for value in removed_values:
        if value in current:
            current.remove(value)
            _append_unique(summary.removed, value)
    for value in added_values:
        if value not in current:
            current.append(value)
            _append_unique(summary.added, value)
    data[field] = current


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
