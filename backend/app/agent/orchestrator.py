import inspect
import json
import logging
import re
from collections.abc import Awaitable, Callable

from app.agent.memory import SessionMemory
from app.agent.intent_context import apply_query_delta, apply_session_context
from app.agent.intent_enhancer import (
    enhance_intent_from_message,
    extract_explicit_trip_fields,
    extract_removed_preferences,
    normalize_avoid_tags,
    normalize_preferences,
)
from app.agent.message_router import MessageIntentType, MessageRouter
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.route_detail_handler import RouteDetailHandler
from app.agent.schemas import IntentDelta, QueryUnderstanding, StateChangeSummary, TripState
from app.llm.provider import get_llm_client
from app.schemas.chat import AgentTraceStep, ChatRequest, ChatResponse
from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import Route
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService


logger = logging.getLogger("app.agent.orchestrator")


class AgentOrchestrator:
    """A-owned module: coordinates intent, profile, POI search, and route planning."""

    def __init__(self) -> None:
        self.memory = SessionMemory()
        self.llm_client = get_llm_client()
        self.message_router = MessageRouter(self.llm_client)
        self.route_detail_handler = RouteDetailHandler()
        self.profile_service = ProfileService()
        self.poi_service = POIService()
        self.route_service = RouteService()

    async def handle_message(
        self,
        request: ChatRequest,
        progress_callback: Callable[[AgentTraceStep], Awaitable[None] | None] | None = None,
    ) -> ChatResponse:
        trace: list[AgentTraceStep] = []
        emitted_trace_count = 0

        async def emit_pending_trace() -> None:
            nonlocal emitted_trace_count
            if progress_callback is None:
                emitted_trace_count = len(trace)
                return
            while emitted_trace_count < len(trace):
                step = trace[emitted_trace_count]
                emitted_trace_count += 1
                result = progress_callback(step)
                if inspect.isawaitable(result):
                    await result

        logger.info(
            "chat start session_id=%s user_id=%s event_type=%s message=%s",
            request.session_id,
            request.user_id,
            request.event_type,
            self._preview(request.message),
        )

        session_state = self.memory.get_state(request.session_id)
        message_route = await self.message_router.classify(request.message, session_state)
        trace.append(
            AgentTraceStep(
                step="route_message",
                label=self._format_message_route_label(message_route),
                status="done",
                details=self._message_route_details(message_route),
            )
        )
        await emit_pending_trace()

        if message_route.intent_type == MessageIntentType.ROUTE_DETAIL_QUESTION:
            response = self.route_detail_handler.answer(request.message, request.session_id, session_state)
            response.agent_trace = [*trace, *response.agent_trace]
            return response

        if message_route.intent_type == MessageIntentType.GENERAL_CHAT:
            return await self._handle_direct_llm_chat(request, trace)

        intent = await self._parse_intent(request.message, trace)
        await emit_pending_trace()
        intent = enhance_intent_from_message(intent, request.message)
        contextual_intent = apply_session_context(intent, request.message, session_state, message_route)
        context_applied = contextual_intent != intent
        if contextual_intent != intent:
            trace.append(
                AgentTraceStep(
                    step="apply_session_context",
                    label="继承上一轮出行上下文",
                    status="done",
                    details=self._intent_trace_details(contextual_intent),
                )
            )
            await emit_pending_trace()
        intent = contextual_intent
        merge_request = request
        if session_state.last_intent and not intent.city_from_message:
            merge_request = request.model_copy(update={"city": None})
        intent = self.profile_service.merge_request_into_intent(intent, merge_request)
        fallback_understanding = self._build_query_understanding(message_route, context_applied)
        fallback_delta = self._build_intent_delta(intent, request.message, session_state, message_route)
        understanding, delta, delta_source = await self._parse_query_delta(
            request.message,
            session_state,
            fallback_understanding,
            fallback_delta,
            trace,
        )
        await emit_pending_trace()
        intent, trip_state, state_summary = apply_query_delta(intent, session_state, understanding, delta)
        delta_details = state_summary.model_dump()
        delta_details["source"] = delta_source
        trace.append(
            AgentTraceStep(
                step="apply_query_delta",
                label=self._format_state_change_summary(state_summary),
                status="done",
                details=delta_details,
            )
        )
        await emit_pending_trace()
        logger.info("chat intent session_id=%s intent=%s", request.session_id, intent.model_dump())

        user_profile = self.profile_service.get_profile(request.user_id, request)
        trace.append(
            AgentTraceStep(
                step="get_user_profile",
                label="读取用户画像",
                status="done",
                details={
                    "preferences": user_profile.preferences,
                    "avoid_tags": user_profile.avoid_tags,
                    "tags": user_profile.tags,
                },
            )
        )
        await emit_pending_trace()
        logger.info("step done session_id=%s step=get_user_profile profile=%s", request.session_id, user_profile.model_dump())

        strategy_weights = self.profile_service.build_strategy_weights(intent, user_profile)
        trace.append(
            AgentTraceStep(
                step="build_strategy_weights",
                label="生成偏好权重",
                status="done",
                details={"weights": strategy_weights.model_dump()},
            )
        )
        await emit_pending_trace()
        logger.info(
            "step done session_id=%s step=build_strategy_weights weights=%s",
            request.session_id,
            strategy_weights.model_dump(),
        )

        pois = self.poi_service.search(intent, user_profile=user_profile)
        trace.append(
            AgentTraceStep(
                step="search_pois",
                label=f"召回 {len(pois)} 个候选 POI",
                status="done",
                details={
                    "count": len(pois),
                    "city": intent.city,
                    "names": [poi.name for poi in pois[:5]],
                },
            )
        )
        await emit_pending_trace()
        logger.info(
            "step done session_id=%s step=search_pois count=%s pois=%s",
            request.session_id,
            len(pois),
            [poi.name for poi in pois],
        )

        routes = self.route_service.generate_routes(
            RoutePlanRequest(intent=intent, user_profile=user_profile, strategy_weights=strategy_weights, candidate_pois=pois)
        ).routes
        trace.append(AgentTraceStep(step="generate_routes", label="生成多目标路线", status="done"))
        trace[-1].details = {
            "count": len(routes),
            "route_titles": [route.title for route in routes[:5]],
            "objectives": [route.objective for route in routes[:5]],
        }
        await emit_pending_trace()
        logger.info(
            "step done session_id=%s step=generate_routes count=%s routes=%s",
            request.session_id,
            len(routes),
            [route.route_id for route in routes],
        )

        message = await self._summarize_route_result(intent, pois, routes, trace)
        await emit_pending_trace()
        message = self._prepend_visible_state_change(message, trip_state, state_summary)

        self.memory.save_turn_result(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=message,
            intent=intent,
            user_profile=user_profile,
            routes=routes,
            trip_state=trip_state,
        )
        logger.info("chat done session_id=%s trace=%s", request.session_id, [step.model_dump() for step in trace])

        return ChatResponse(
            session_id=request.session_id,
            message=message,
            need_clarification=False,
            clarifying_question=None,
            intent=intent,
            user_profile=user_profile,
            routes=routes,
            agent_trace=trace,
        )

    def _format_message_route_label(self, message_route) -> str:
        route_label = self._turn_type_label(message_route.turn_type.value if message_route.turn_type else "")
        if not route_label:
            route_label = self._intent_type_label(message_route.intent_type.value)
        suffixes: list[str] = []
        if message_route.inherit_previous:
            suffixes.append("继承上一轮上下文")
        if message_route.preserve_scenario:
            suffixes.append("保留原出行场景")
        if message_route.references_previous_route:
            suffixes.append("引用上一轮路线")
        return "判定为：" + route_label + (f"，{ '，'.join(suffixes) }" if suffixes else "")

    def _message_route_details(self, message_route) -> dict[str, object]:
        turn_type = message_route.turn_type.value if message_route.turn_type else None
        intent_type = message_route.intent_type.value
        return {
            "intent_type": intent_type,
            "intent_type_label": self._intent_type_label(intent_type),
            "turn_type": turn_type,
            "turn_type_label": self._turn_type_label(turn_type or ""),
            "inherit_previous": message_route.inherit_previous,
            "preserve_scenario": message_route.preserve_scenario,
            "references_previous_route": message_route.references_previous_route,
            "question_type": message_route.detail_type,
            "confidence": round(message_route.confidence, 2),
        }

    def _intent_type_label(self, intent_type: str) -> str:
        return {
            "new_plan": "新规划",
            "modify_plan": "修改已有路线",
            "route_detail_question": "路线追问",
            "general_chat": "普通聊天",
        }.get(intent_type, intent_type)

    def _turn_type_label(self, turn_type: str) -> str:
        return {
            "new_plan": "新规划",
            "add_constraint": "补充需求",
            "modify_constraint": "修改条件",
            "remove_constraint": "移除条件",
            "route_detail": "路线追问",
            "general_chat": "普通聊天",
        }.get(turn_type, turn_type)

    def _intent_trace_details(self, intent: Intent) -> dict[str, object]:
        return {
            "city": intent.city,
            "people_count": intent.people_count,
            "start_time": intent.start_time,
            "duration_hours": intent.duration_hours,
            "budget_per_person": intent.budget_per_person,
            "preferences": intent.preferences,
            "avoid_tags": intent.avoid_tags,
            "scenario": intent.scenario,
        }

    async def _parse_query_delta(
        self,
        message: str,
        session_state,
        fallback_understanding: QueryUnderstanding,
        fallback_delta: IntentDelta,
        trace: list[AgentTraceStep],
    ) -> tuple[QueryUnderstanding, IntentDelta, str]:
        if not session_state.last_intent and not session_state.trip_state:
            return fallback_understanding, fallback_delta, "initial_intent_snapshot"

        try:
            payload = await self._llm_parse_query_delta(message, session_state)
            understanding = QueryUnderstanding.model_validate(payload.get("understanding", {}))
            delta = IntentDelta.model_validate(payload.get("delta", {}))
            delta = self._normalize_intent_delta(delta)
            trace.append(
                AgentTraceStep(
                    step="parse_query_delta",
                    label="LLM 解析本轮状态变更",
                    status="done",
                    details={
                        "turn_type": understanding.turn_type,
                        "inherit_previous": understanding.inherit_previous,
                        "preserve_scenario": understanding.preserve_scenario,
                        "confidence": understanding.confidence,
                        "delta": delta.model_dump(),
                    },
                )
            )
            return understanding, delta, "llm_structured_delta"
        except Exception as exc:
            logger.exception("step failed step=parse_query_delta mode=llm fallback=true error=%s", type(exc).__name__)
            trace.append(
                AgentTraceStep(
                    step="parse_query_delta",
                    label=f"LLM 状态变更解析失败，使用规则兜底：{type(exc).__name__}",
                    status="fallback",
                    details={"delta": fallback_delta.model_dump()},
                )
            )
            return fallback_understanding, fallback_delta, "rule_fallback_delta"

    async def _llm_parse_query_delta(self, message: str, session_state) -> dict:
        schema = {
            "understanding": {
                "turn_type": ["new_plan", "add_constraint", "modify_constraint", "remove_constraint", "route_detail", "general_chat"],
                "inherit_previous": "boolean",
                "preserve_scenario": "boolean",
                "target_route_ref": "current or null",
                "target_stop_ref": "string or null",
                "question_type": "string or null",
                "confidence": "0-1 number",
                "reason": "short Chinese reason",
            },
            "delta": {
                "added_hard_constraints": "object",
                "modified_hard_constraints": "object; explicit user changes such as people_count=2",
                "removed_hard_constraints": "array",
                "added_preferences": "array using canonical labels",
                "removed_preferences": "array using canonical labels",
                "added_avoid_tags": "array using canonical labels",
                "removed_avoid_tags": "array using canonical labels",
                "added_implicit_needs": "array",
                "removed_implicit_needs": "array",
                "added_must_include": "array such as meal_stop/rest_stop",
                "removed_must_include": "array such as meal_stop/rest_stop",
            },
        }
        allowed = self._delta_allowed_values()
        previous_state = session_state.trip_state.model_dump() if session_state.trip_state else None
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "你是路线规划 Agent 的状态变更解析器，只输出 JSON object。"
                        "你的任务不是重写完整 Intent，而是比较用户本轮消息和上一轮 TripState，输出 QueryUnderstanding 和 IntentDelta。"
                        "本轮用户明确说出的硬约束必须进入 modified_hard_constraints，例如人数、时长、预算、开始时间、城市。"
                        "用户否定的偏好必须进入 removed_preferences 或 removed_must_include。"
                        "不要发明标签；preferences/avoid_tags/must_include 只能使用允许值。"
                        "如果只是隐含建议升级为显式必须，只写 added_must_include 和 removed_implicit_needs。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": message,
                            "previous_trip_state": previous_state,
                            "has_previous_intent": session_state.last_intent is not None,
                            "schema": schema,
                            "allowed_values": allowed,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            json_mode=True,
        )
        content = response["choices"][0]["message"]["content"]
        return self._load_json_object(content)

    def _normalize_intent_delta(self, delta: IntentDelta) -> IntentDelta:
        data = delta.model_dump()
        data["added_preferences"] = self._filter_allowed_preferences(normalize_preferences(data["added_preferences"]))
        data["removed_preferences"] = self._filter_allowed_preferences(normalize_preferences(data["removed_preferences"]))
        data["added_avoid_tags"] = self._filter_allowed_avoid_tags(normalize_avoid_tags(data["added_avoid_tags"]))
        data["removed_avoid_tags"] = self._filter_allowed_avoid_tags(normalize_avoid_tags(data["removed_avoid_tags"]))
        data["added_implicit_needs"] = self._filter_allowed_needs(data["added_implicit_needs"])
        data["removed_implicit_needs"] = self._filter_allowed_needs(data["removed_implicit_needs"])
        data["added_must_include"] = self._filter_allowed_needs(data["added_must_include"])
        data["removed_must_include"] = self._filter_allowed_needs(data["removed_must_include"])
        data["added_hard_constraints"] = self._filter_hard_constraints(data["added_hard_constraints"])
        data["modified_hard_constraints"] = self._filter_hard_constraints(data["modified_hard_constraints"])
        return IntentDelta.model_validate(data)

    def _delta_allowed_values(self) -> dict[str, list[str]]:
        return {
            "preferences": ["吃好", "少排队", "更省钱", "少走路", "citywalk", "拍照", "亲子友好", "室内", "安静", "朋友同行"],
            "avoid_tags": ["人流密集", "排队久", "太贵", "商业街", "辣", "步行多"],
            "needs": ["meal_stop", "rest_stop"],
            "hard_constraints": ["city", "people_count", "start_time", "duration_hours", "budget_per_person", "scenario"],
        }

    def _filter_allowed_preferences(self, values: list[str]) -> list[str]:
        allowed = set(self._delta_allowed_values()["preferences"])
        return [value for value in values if value in allowed]

    def _filter_allowed_avoid_tags(self, values: list[str]) -> list[str]:
        allowed = set(self._delta_allowed_values()["avoid_tags"])
        return [value for value in values if value in allowed]

    def _filter_allowed_needs(self, values: list[str]) -> list[str]:
        allowed = set(self._delta_allowed_values()["needs"])
        return [value for value in values if value in allowed]

    def _filter_hard_constraints(self, values: dict[str, object]) -> dict[str, object]:
        allowed = set(self._delta_allowed_values()["hard_constraints"])
        result: dict[str, object] = {}
        for key, value in values.items():
            if key not in allowed:
                continue
            if key in {"people_count", "duration_hours", "budget_per_person"}:
                result[key] = self._coerce_int(value, 0)
            elif key in {"city", "start_time", "scenario"} and value:
                result[key] = str(value)
        return result

    def _build_query_understanding(self, message_route, context_applied: bool) -> QueryUnderstanding:
        return QueryUnderstanding(
            turn_type=message_route.turn_type.value if message_route.turn_type else message_route.intent_type.value,
            inherit_previous=message_route.inherit_previous or context_applied,
            preserve_scenario=message_route.preserve_scenario,
            target_route_ref="current" if message_route.references_previous_route else None,
            question_type=message_route.detail_type,
            confidence=message_route.confidence,
            reason="message_router",
        )

    def _build_intent_delta(
        self,
        intent: Intent,
        message: str,
        session_state,
        message_route,
    ) -> IntentDelta:
        previous_state = session_state.trip_state
        if previous_state is None and session_state.last_intent:
            previous_state = TripState.from_intent(session_state.last_intent)

        explicit_fields = extract_explicit_trip_fields(message)
        previous_preferences = set(normalize_preferences(previous_state.soft_preferences) if previous_state else [])
        previous_avoid_tags = set(normalize_avoid_tags(previous_state.avoid_tags) if previous_state else [])
        current_preferences = normalize_preferences(intent.preferences)
        current_avoid_tags = normalize_avoid_tags(intent.avoid_tags)
        removed_preferences = extract_removed_preferences(message)
        delta = IntentDelta(
            added_preferences=[
                preference
                for preference in current_preferences
                if preference not in previous_preferences and preference not in removed_preferences
            ],
            removed_preferences=[preference for preference in removed_preferences if preference in previous_preferences or preference in current_preferences],
            added_avoid_tags=[avoid_tag for avoid_tag in current_avoid_tags if avoid_tag not in previous_avoid_tags],
        )

        if previous_state and intent.city_from_message and intent.city != previous_state.city:
            delta.modified_hard_constraints["city"] = intent.city
        if previous_state:
            for field in ("people_count", "duration_hours", "start_time", "budget_per_person"):
                if field in explicit_fields:
                    value = explicit_fields[field]
                    if getattr(previous_state, field) != value:
                        delta.modified_hard_constraints[field] = value

        if self._message_removes_meal_stop(message):
            if "meal_stop" not in delta.removed_must_include:
                delta.removed_must_include.append("meal_stop")
            if "meal_stop" not in delta.removed_implicit_needs:
                delta.removed_implicit_needs.append("meal_stop")
        elif self._message_requests_meal_stop(message, delta.added_preferences, message_route):
            if "meal_stop" not in delta.added_must_include:
                delta.added_must_include.append("meal_stop")
            if "meal_stop" not in delta.removed_implicit_needs:
                delta.removed_implicit_needs.append("meal_stop")

        return delta

    def _message_removes_meal_stop(self, message: str) -> bool:
        return bool(extract_removed_preferences(message))

    def _message_requests_meal_stop(self, message: str, added_preferences: list[str], message_route) -> bool:
        meal_terms = ["吃饭", "吃好", "餐厅", "美食", "小吃", "晚饭", "午饭", "饭"]
        is_add_constraint = bool(message_route.turn_type and message_route.turn_type.value == "add_constraint")
        return is_add_constraint and ("吃好" in added_preferences or any(term in message for term in meal_terms))

    def _format_state_change_summary(self, summary: StateChangeSummary) -> str:
        parts: list[str] = []
        if summary.kept:
            parts.append("保留 " + "、".join(summary.kept))
        if summary.added:
            parts.append("新增 " + "、".join(summary.added))
        if summary.changed:
            changed = [f"{key}:{value['from']}->{value['to']}" for key, value in summary.changed.items()]
            parts.append("修改 " + "、".join(changed))
        if summary.removed:
            parts.append("移除 " + "、".join(summary.removed))
        return "；".join(parts) if parts else "状态无显式变更"

    def _prepend_visible_state_change(self, message: str, trip_state: TripState, summary: StateChangeSummary) -> str:
        prefix = self._format_visible_state_change(trip_state, summary)
        if not prefix:
            return message
        return f"{prefix}\n{message}"

    def _format_visible_state_change(self, trip_state: TripState, summary: StateChangeSummary) -> str:
        if not (summary.added or summary.changed or summary.removed):
            return ""

        parts: list[str] = []
        kept_values = self._visible_kept_values(trip_state, summary)
        if kept_values:
            parts.append("我保留了" + "、".join(kept_values) + "的设定")

        changed_values = [
            f"{self._state_field_label(key)}从{value['from']}改为{value['to']}"
            for key, value in summary.changed.items()
        ]
        if changed_values:
            parts.append("把" + "、".join(changed_values))

        added_values = self._visible_change_values(summary.added)
        if added_values:
            parts.append("新增了" + "、".join(added_values))

        removed_values = self._visible_change_values([value for value in summary.removed if value not in summary.added])
        if removed_values:
            parts.append("移除了" + "、".join(removed_values))

        return "，".join(parts) + "。" if parts else ""

    def _visible_kept_values(self, trip_state: TripState, summary: StateChangeSummary) -> list[str]:
        values: list[str] = []
        if "city" in summary.kept:
            values.append(trip_state.city)
        if "people_count" in summary.kept:
            values.append(f"{trip_state.people_count}人")
        if "duration_hours" in summary.kept:
            values.append(f"{trip_state.duration_hours}小时")

        added = set(summary.added)
        for preference in trip_state.soft_preferences:
            if preference not in added:
                values.append(preference)
        return values

    def _visible_change_values(self, values: list[str]) -> list[str]:
        labels = {
            "meal_stop": "吃饭节点",
            "rest_stop": "休息节点",
        }
        result: list[str] = []
        for value in values:
            label = labels.get(value, value)
            if label not in result:
                result.append(label)
        return result

    def _state_field_label(self, field: str) -> str:
        return {
            "city": "城市",
            "people_count": "人数",
            "duration_hours": "时长",
            "start_time": "开始时间",
            "budget_per_person": "预算",
            "scenario": "场景",
        }.get(field, field)

    async def _summarize_route_result(self, intent: Intent, pois: list[POI], routes: list[Route], trace: list[AgentTraceStep]) -> str:
        fallback_message = self._build_route_summary_fallback(routes)
        logger.info("step start step=summarize_routes mode=llm pois=%s routes=%s", len(pois), len(routes))

        if not routes:
            trace.append(AgentTraceStep(step="summarize_routes", label="候选点不足，未生成路线", status="fallback"))
            return f"当前在{intent.city}可用候选点不足，还没有生成可执行路线。你可以换一个城市，或者补充更具体的区域、景点类型和预算偏好，我再继续规划。"

        try:
            summary_input = {
                "intent": intent.model_dump(),
                "candidate_pois": [
                    {
                        "name": poi.name,
                        "city": poi.city,
                        "category": poi.category,
                        "avg_price": poi.avg_price,
                        "rating": poi.rating,
                        "queue_minutes": poi.queue_minutes,
                        "visit_duration_minutes": poi.visit_duration_minutes,
                        "tags": poi.tags,
                        "negative_tags": poi.negative_tags,
                    }
                    for poi in pois[:8]
                ],
                "routes": [
                    {
                        "title": route.title,
                        "objective": route.objective,
                        "summary": route.summary,
                        "total_duration_minutes": route.total_duration_minutes,
                        "total_cost_per_person": route.total_cost_per_person,
                        "total_queue_minutes": route.total_queue_minutes,
                        "total_travel_minutes": route.total_travel_minutes,
                        "total_distance_km": route.total_distance_km,
                        "score": route.score,
                        "stops": [
                            {
                                "name": stop.name,
                                "category": stop.category,
                                "district": stop.district,
                                "address": stop.address,
                                "start_time": stop.start_time,
                                "end_time": stop.end_time,
                                "estimated_cost": stop.estimated_cost,
                                "queue_minutes": stop.queue_minutes,
                                "travel_minutes_from_previous": stop.travel_minutes_from_previous,
                                "distance_km_from_previous": stop.distance_km_from_previous,
                                "transport_mode_from_previous": stop.transport_mode_from_previous,
                                "walking_intensity": stop.walking_intensity,
                                "recommended_transport": stop.recommended_transport,
                                "highlight_text": stop.highlight_text,
                                "ugc_tip": stop.ugc_tip,
                                "reason": stop.reason,
                                "tags": stop.tags,
                            }
                            for stop in route.stops
                        ],
                        "reasons": route.reasons,
                    }
                    for route in routes[:3]
                ],
            }
            logger.info("summarize_routes input=%s", summary_input)
            response = await self.llm_client.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是路线规划 Agent 的结果总结器。"
                            "根据已召回的 POI 和已生成的路线，用中文给用户做一个简短总结。"
                            "只总结给定内容，不要编造不存在的地点或路线。"
                            "当 routes 不为空时，优先把结构化路线字段写进用户可见文本："
                            "用 total_distance_km 和 total_travel_minutes 说明整体距离和交通时间；"
                            "用 stop.reason、highlight_text、ugc_tip 解释为什么推荐、有什么亮点和避坑；"
                            "用 transport_mode_from_previous、distance_km_from_previous、travel_minutes_from_previous 说明站点之间怎么走。"
                            "字段为空时跳过，不要编造。"
                            "如果 routes 为空，说明候选点不足，并建议用户换城市或补充偏好。"
                            "回复控制在 2 到 4 句话。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(summary_input, ensure_ascii=False),
                    },
                ],
                json_mode=False,
            )
            content = response["choices"][0]["message"]["content"].strip()
            trace.append(AgentTraceStep(step="summarize_routes", label="LLM 总结召回和路线结果", status="done"))
            logger.info("step done step=summarize_routes mode=llm content=%s", self._preview(content))
            return content or fallback_message
        except Exception as exc:
            unavailable_message = (
                f"LLM 总结不可用（{type(exc).__name__}），以下先展示路线引擎生成的结构化结果："
                f"{fallback_message}"
            )
            trace.append(
                AgentTraceStep(
                    step="summarize_routes",
                    label=f"LLM 总结不可用，使用结构化路线结果：{type(exc).__name__}",
                    status="fallback",
                )
            )
            logger.exception("step failed step=summarize_routes mode=llm fallback=true error=%s", type(exc).__name__)
            return unavailable_message

    def _build_route_summary_fallback(self, routes: list[Route]) -> str:
        if not routes:
            return "我先按你们的需求生成了几条可执行路线，后续可以继续让我少排队、更省钱或换一家。"

        route = routes[0]
        parts = [f"我先推荐「{route.title}」"]
        metrics: list[str] = []
        if route.total_duration_minutes:
            metrics.append(f"总时长约 {route.total_duration_minutes} 分钟")
        if route.total_distance_km:
            metrics.append(f"路程约 {route.total_distance_km:g} 公里")
        if route.total_travel_minutes:
            metrics.append(f"交通约 {route.total_travel_minutes} 分钟")
        if route.total_cost_per_person:
            metrics.append(f"人均约 {route.total_cost_per_person} 元")
        if route.total_queue_minutes:
            metrics.append(f"排队约 {route.total_queue_minutes} 分钟")
        if metrics:
            parts.append("，" + "，".join(metrics))
        parts.append("。")

        detail_lines: list[str] = []
        for stop in route.stops:
            stop_bits = [value for value in [stop.reason, stop.highlight_text, stop.ugc_tip] if value]
            if stop_bits:
                detail_lines.append(f"{stop.name}：" + "；".join(stop_bits))
            if len(detail_lines) >= 1:
                break

        leg = next(
            (
                stop
                for stop in route.stops
                if stop.transport_mode_from_previous
                or stop.distance_km_from_previous
                or stop.travel_minutes_from_previous
            ),
            None,
        )
        if leg:
            leg_bits: list[str] = []
            if leg.transport_mode_from_previous:
                leg_bits.append(f"建议{self._format_transport_mode(leg.transport_mode_from_previous)}")
            if leg.travel_minutes_from_previous:
                leg_bits.append(f"约 {leg.travel_minutes_from_previous} 分钟")
            if leg.distance_km_from_previous:
                leg_bits.append(f"约 {leg.distance_km_from_previous:g} 公里")
            if leg_bits:
                detail_lines.append(f"到{leg.name}这段" + "，".join(leg_bits))

        if detail_lines:
            parts.append(" ".join(detail_lines[:3]) + "。")
        if route.reasons:
            parts.append("推荐理由：" + "、".join(route.reasons[:3]) + "。")
        return "".join(parts)

    def _format_transport_mode(self, mode: str) -> str:
        mode_labels = {
            "walk": "步行",
            "metro": "地铁",
            "taxi": "打车",
            "bike": "骑行",
            "bus": "公交",
            "drive": "自驾",
        }
        modes = [part for part in mode.split("/") if part]
        if len(modes) > 1:
            return "或".join(mode_labels.get(part, part) for part in modes)
        return mode_labels.get(mode, mode)

    async def _handle_direct_llm_chat(self, request: ChatRequest, trace: list[AgentTraceStep]) -> ChatResponse:
        logger.info("chat direct_llm start session_id=%s reason=not_route_related", request.session_id)
        try:
            response = await self.llm_client.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "你是一个用于测试接入链路的中文助手。"
                            "当前消息和路线规划无关时，直接自然回复用户。"
                            "回复要简短，不要生成路线 JSON。"
                        ),
                    },
                    {"role": "user", "content": request.message},
                ],
                json_mode=False,
            )
            content = response["choices"][0]["message"]["content"]
            trace.append(AgentTraceStep(step="direct_llm_chat", label="非路线问题，直接 LLM 对话", status="done"))
            logger.info("chat direct_llm done session_id=%s content=%s", request.session_id, self._preview(content))
            return ChatResponse(
                session_id=request.session_id,
                message=content,
                need_clarification=False,
                clarifying_question=None,
                intent=None,
                user_profile=None,
                routes=[],
                agent_trace=trace,
            )
        except Exception as exc:
            trace.append(
                AgentTraceStep(
                    step="direct_llm_chat",
                    label=f"直接 LLM 对话失败：{type(exc).__name__}",
                    status="error",
                )
            )
            logger.exception("chat direct_llm failed session_id=%s error=%s", request.session_id, type(exc).__name__)
            return ChatResponse(
                session_id=request.session_id,
                message="直接 LLM 对话暂时失败了，但后端链路还在。你可以看终端日志定位具体错误。",
                need_clarification=False,
                clarifying_question=None,
                intent=None,
                user_profile=None,
                routes=[],
                agent_trace=trace,
            )

    def _looks_route_related(self, message: str) -> bool:
        text = message.strip().lower()
        if not text:
            return False

        route_keywords = [
            "路线",
            "规划",
            "行程",
            "出行",
            "旅游",
            "旅行",
            "游玩",
            "citywalk",
            "逛",
            "玩",
            "景点",
            "餐厅",
            "咖啡",
            "拍照",
            "预算",
            "排队",
            "便宜",
            "省钱",
            "亲子",
            "朋友",
            "情侣",
            "人均",
            "小时",
            "分钟",
            "上午",
            "下午",
            "晚上",
            "点",
            "上海",
            "杭州",
            "北京",
            "广州",
            "深圳",
            "南京",
            "成都",
            "重庆",
            "苏州",
        ]
        if any(keyword in text for keyword in route_keywords):
            return True

        return bool(re.search(r"\d+\s*(人|个|点|小时|分钟|元|块)", text))

    async def _parse_intent(self, message: str, trace: list[AgentTraceStep]) -> Intent:
        try:
            logger.info("step start step=parse_intent mode=llm")
            intent = await self._llm_parse_intent(message)
            trace.append(
                AgentTraceStep(
                    step="parse_intent",
                    label="LLM 解析用户意图",
                    status="done",
                    details=self._intent_trace_details(intent),
                )
            )
            logger.info("step done step=parse_intent mode=llm")
            return intent
        except Exception as exc:
            logger.exception("step failed step=parse_intent mode=llm fallback=true error=%s", type(exc).__name__)
            intent = self._mock_parse_intent(message)
            trace.append(
                AgentTraceStep(
                    step="parse_intent",
                    label=f"LLM 解析失败，使用 fallback：{type(exc).__name__}",
                    status="fallback",
                    details=self._intent_trace_details(intent),
                )
            )
            logger.info("step done step=parse_intent mode=fallback intent=%s", intent.model_dump())
            return intent

    async def _llm_parse_intent(self, message: str) -> Intent:
        schema_fields = {
            "city": "string, default 上海 when omitted",
            "people_count": "integer",
            "start_time": "HH:MM string",
            "duration_hours": "integer",
            "budget_per_person": "integer, CNY",
            "start_location_name": "string or null, route start place name when mentioned",
            "start_lat": "number or null, route start latitude when known",
            "start_lng": "number or null, route start longitude when known",
            "preferences": "array of short Chinese strings",
            "avoid_tags": "array of short Chinese strings",
            "scenario": "short snake_case string",
            "need_clarification": "boolean",
        }
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        f"{SYSTEM_PROMPT}\n"
                        "你只负责把用户消息解析成路线规划 Intent。"
                        "必须只返回一个 JSON object，不要 Markdown，不要解释。"
                        "无论信息是否完整，都必须包含所有字段。"
                        "用户只打招呼或需求不清时，用默认值补齐字段，并把 need_clarification 设为 true。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"字段说明：{json.dumps(schema_fields, ensure_ascii=False)}\n用户消息：{message}",
                },
            ]
        )
        content = response["choices"][0]["message"]["content"]
        logger.info("intent raw_llm_content=%s", self._preview(content))
        parsed = Intent().model_dump()
        loaded = self._load_json_object(content)
        logger.info("intent loaded_json=%s", loaded)
        parsed.update(loaded)
        parsed = self._normalize_intent_data(parsed)
        logger.info("intent normalized_json=%s", parsed)
        return Intent.model_validate(parsed)

    def _load_json_object(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _normalize_intent_data(self, data: dict) -> dict:
        defaults = Intent().model_dump()
        normalized = defaults | data

        for key in ("city", "start_time", "scenario"):
            if not normalized.get(key):
                normalized[key] = defaults[key]
            else:
                normalized[key] = str(normalized[key])

        if normalized.get("start_location_name") is not None:
            normalized["start_location_name"] = str(normalized["start_location_name"])

        for key in ("start_lat", "start_lng"):
            normalized[key] = self._coerce_optional_float(normalized.get(key))

        for key in ("people_count", "duration_hours", "budget_per_person"):
            normalized[key] = self._coerce_int(normalized.get(key), defaults[key])
            if normalized[key] <= 0:
                normalized[key] = defaults[key]

        for key in ("preferences", "avoid_tags"):
            normalized[key] = self._coerce_string_list(normalized.get(key))

        value = normalized.get("need_clarification", defaults["need_clarification"])
        if isinstance(value, str):
            normalized["need_clarification"] = value.strip().lower() in {"true", "1", "yes", "y", "是", "需要"}
        elif value is None:
            normalized["need_clarification"] = defaults["need_clarification"]
        else:
            normalized["need_clarification"] = bool(value)

        return normalized

    def _coerce_int(self, value: object, default: int) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            digits = re.search(r"\d+", value)
            if digits:
                return int(digits.group(0))
            chinese_numbers = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            for char, number in chinese_numbers.items():
                if char in value:
                    return number
        return default

    def _coerce_optional_float(self, value: object) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value)
            if match:
                return float(match.group(0))
        return None

    def _coerce_string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,，、/|]", value) if item.strip()]
        return [str(value)]

    def _preview(self, value: str, limit: int = 800) -> str:
        return value if len(value) <= limit else f"{value[:limit]}..."

    def _mock_parse_intent(self, message: str) -> Intent:
        preferences = []
        if any(term in message for term in ["吃好", "美食", "餐厅", "小吃"]):
            preferences.append("吃好")
        if any(term in message for term in ["少排队", "别排队", "不排队", "不想排队"]):
            preferences.append("少排队")
        if any(term in message for term in ["拍照", "出片", "打卡", "citywalk", "街区"]):
            preferences.append("拍照")
        if any(term in message for term in ["少走路", "轻松", "别太累", "不要太累"]):
            preferences.append("少走路")
        if "省钱" in message or "便宜" in message:
            preferences.append("更省钱")
        if "亲子" in message or "小孩" in message:
            preferences.append("亲子友好")

        avoid_tags = []
        if any(term in message for term in ["人多", "拥挤", "人流密集"]):
            avoid_tags.append("人流密集")
        if any(term in message for term in ["排队久", "排队太久"]):
            avoid_tags.append("排队久")
        if any(term in message for term in ["太贵", "贵"]):
            avoid_tags.append("太贵")

        return Intent(
            city="上海",
            people_count=3 if "三" in message or "3" in message else 2,
            start_time="14:00",
            duration_hours=6,
            budget_per_person=300,
            preferences=preferences,
            avoid_tags=avoid_tags,
            scenario="friends_citywalk",
            need_clarification=False,
        )
