import asyncio
import inspect
import json
import logging
import math
import re
from collections.abc import Awaitable, Callable

from app.agent.demo_mock import build_mock_trace, build_mock_routes, build_demo_clarification, is_demo_trigger, stream_mock_trace
from app.agent.memory import SessionMemory
from app.agent.intent_context import apply_query_delta, apply_session_context
from app.agent.intent_enhancer import (
    enhance_intent_from_message,
    extract_explicit_trip_fields,
    extract_removed_preferences,
    normalize_avoid_tags,
    normalize_preferences,
)
from app.agent.unit_normalizer import extract_standard_unit_fields
from app.agent.clarification_policy import ClarificationDecision, ClarificationPolicy
from app.agent.message_router import MessageIntentType, MessageRouter, PlanningMode
from app.agent.prompts import (
    DIRECT_CHAT_SYSTEM_PROMPT,
    ROUTE_SUMMARY_SYSTEM_PROMPT,
    STATE_DELTA_SYSTEM_PROMPT,
    build_intent_parser_system_prompt,
)
from app.agent.replan_intent_parser import ReplanIntentParser
from app.agent.route_detail_handler import RouteDetailHandler
from app.agent.schemas import IntentDelta, QueryUnderstanding, StateChangeSummary, TripState
from app.agent.unit_normalizer import normalize_delta_units
from app.llm.provider import get_llm_client
from app.schemas.chat import AgentTraceStep, ChatRequest, ChatResponse
from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import ReplanRequest, Route
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.fine_rank_service import FineRankService
from app.services.profile_service import ProfileService
from app.services.replan_service import ReplanService
from app.services.route_service import RouteService


logger = logging.getLogger("app.agent.orchestrator")


class AgentOrchestrator:
    """A-owned module: coordinates intent, profile, POI search, and route planning."""

    DEFAULT_CITY_STARTS = {
        "上海": {"name": "静安寺站", "lat": 31.2231, "lng": 121.4466},
        "北京": {"name": "西单站", "lat": 39.9072, "lng": 116.3740},
    }

    def __init__(self) -> None:
        self.memory = SessionMemory()
        self.llm_client = get_llm_client()
        self.message_router = MessageRouter(self.llm_client)
        self.clarification_policy = ClarificationPolicy()
        self.replan_intent_parser = ReplanIntentParser()
        self.route_detail_handler = RouteDetailHandler()
        self.profile_service = ProfileService()
        self.poi_service = POIService()
        self.fine_rank_service = FineRankService()
        self.route_service = RouteService()
        self.replan_service = ReplanService()

    async def handle_message(
        self,
        request: ChatRequest,
        progress_callback: Callable[[AgentTraceStep], Awaitable[None] | None] | None = None,
        routes_callback: Callable[[list[Route]], Awaitable[None] | None] | None = None,
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

        async def emit_routes(routes: list[Route]) -> None:
            if routes_callback is None:
                return
            result = routes_callback(routes)
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
        if self._is_structured_replan_request(request, session_state):
            return self._handle_structured_replan(request, session_state, trace)

        # ── 并行加速：首轮新对话时，route_message 分类和 parse_intent 可以同时跑 ──────
        # 非首轮（有 last_intent）时仍串行，因为 parse_intent 需要等 route 结果决定是否继承上下文。
        is_first_turn = session_state.last_intent is None
        if is_first_turn:
            message_route, intent_prefetch = await asyncio.gather(
                self.message_router.classify(request.message, session_state),
                self._llm_parse_intent_safe(request.message, request),
            )
        else:
            message_route = await self.message_router.classify(request.message, session_state)
            intent_prefetch = None

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

        if message_route.planning_mode == PlanningMode.PARTIAL_REPLAN and session_state.current_routes:
            partial_response = self._handle_partial_replan(request, session_state, trace)
            if partial_response:
                return partial_response

        # 使用预取到的 intent（首轮），或重新解析（非首轮）
        intent = await self._parse_intent(request.message, trace, request, prefetched=intent_prefetch)
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

        # ── Demo 追问拦截：第一轮命中触发词且无 target_district 时，直接返回预设追问卡片 ──
        # 这样不依赖 clarification_policy（会被 GPS 起点绕过），保证 demo 流程必问区域
        _demo_clarify_msg = request.message or ""
        _demo_has_district = bool(intent.target_district or request.target_district)
        _demo_is_new_plan = (not session_state) or (
            not session_state.recent_messages
        ) or message_route.planning_mode == PlanningMode.NEW_PLAN
        _demo_clarify_city = intent.city or request.city or "北京"
        if (
            is_demo_trigger(_demo_clarify_msg)
            and not _demo_has_district
            and _demo_clarify_city == "北京"
        ):
            logger.info(
                "demo_clarification session_id=%s msg=%s",
                request.session_id,
                _demo_clarify_msg[:30],
            )
            # 从 GPS 或起点名称推断当前区
            _gps_district = "西城区"
            if request.start_location_name and "西城" in request.start_location_name:
                _gps_district = "西城区"
            elif request.start_location_name and "朝阳" in request.start_location_name:
                _gps_district = "朝阳区"
            elif request.start_location_name and "海淀" in request.start_location_name:
                _gps_district = "海淀区"
            return build_demo_clarification(
                session_id=request.session_id,
                message=_demo_clarify_msg,
                city=_demo_clarify_city,
                current_district=_gps_district,
                trace=trace,
            )

        # ── 追问判断必须在应用默认起点之前执行 ──────────────────────────────
        # 若先执行 _apply_default_city_start，会把 intent.start_location_name 设为"西单站"等默认值，
        # 导致 _is_missing_city 误判为"用户已提供具体地点"而跳过城市/区域追问。
        clarification = self.clarification_policy.evaluate(
            request=request,
            intent=intent,
            message_route=message_route,
            session_state=session_state,
        )
        if clarification.need_clarification:
            return self._handle_clarification(request, session_state, trace, clarification, intent)

        # ── 追问通过后再应用起点：优先 GPS，兜底默认商圈 ────────────────────
        # 优先使用前端传来的 GPS 坐标作为起点（LLM 不会输出具体坐标）
        # 但若 GPS 距城市 POI 过远（> 8km），则 fallback 到默认商圈起点，避免时间窗口不足
        if intent.start_lat is None and intent.start_lng is None:
            if request.start_lat is not None and request.start_lng is not None:
                city_pois = self.poi_service.search(Intent(city=intent.city), limit=5)
                min_dist = self._min_distance_to_pois(request.start_lat, request.start_lng, city_pois)
                if min_dist is not None and min_dist <= 8.0:
                    intent = intent.model_copy(update={
                        "start_lat": request.start_lat,
                        "start_lng": request.start_lng,
                        "start_location_name": intent.start_location_name or "当前位置",
                    })
                    trace.append(
                        AgentTraceStep(
                            step="apply_gps_start",
                            label=f"使用GPS坐标作为起点：({request.start_lat:.4f}, {request.start_lng:.4f})",
                            status="done",
                            details={
                                "start_lat": request.start_lat,
                                "start_lng": request.start_lng,
                                "min_dist_to_poi_km": round(min_dist, 1) if min_dist is not None else None,
                                "reason": "使用前端传入的 GPS 坐标作为规划起点。",
                            },
                        )
                    )
                    await emit_pending_trace()
                # else: GPS 距 POI 太远，走下面的默认商圈逻辑
        intent, default_start = self._apply_default_city_start(intent)
        if default_start:
            trace.append(
                AgentTraceStep(
                    step="apply_default_start",
                    label=f"使用{intent.city}默认起点：{default_start['name']}",
                    status="done",
                    details={
                        "city": intent.city,
                        "start_location_name": default_start["name"],
                        "start_lat": default_start["lat"],
                        "start_lng": default_start["lng"],
                        "reason": "用户未提供起点坐标，使用 demo 城市商圈默认起点。",
                    },
                )
            )
            await emit_pending_trace()

        user_profile = self._profile_for_turn(request, session_state, intent)
        trace.append(
            AgentTraceStep(
                step="get_user_profile",
                label="读取并更新用户画像",
                status="done",
                details={
                    "preferences": user_profile.preferences,
                    "interest_tags": user_profile.interest_tags,
                    "optimization_goals": user_profile.optimization_goals,
                    "avoid_tags": user_profile.avoid_tags,
                    "tags": user_profile.tags,
                    "budget_sensitivity": user_profile.budget_sensitivity,
                    "walking_tolerance": user_profile.walking_tolerance,
                    "crowd_tolerance": user_profile.crowd_tolerance,
                    "category_preferences": user_profile.category_preferences,
                    "preferred_route_roles": user_profile.preferred_route_roles,
                    "preferred_experience_tags": user_profile.preferred_experience_tags,
                },
            )
        )
        await emit_pending_trace()
        logger.info("step done session_id=%s step=get_user_profile profile=%s", request.session_id, user_profile.model_dump())

        strategy_tags = self.profile_service.strategy_service.infer_tags(request.message, intent, user_profile)
        trace.append(
            AgentTraceStep(
                step="derive_strategy_tags",
                label="生成本轮策略标签",
                status="done",
                details={"strategy_tags": [tag.model_dump() for tag in strategy_tags]},
            )
        )
        await emit_pending_trace()
        logger.info(
            "step done session_id=%s step=derive_strategy_tags tags=%s",
            request.session_id,
            [tag.model_dump() for tag in strategy_tags],
        )

        strategy_weights = self.profile_service.build_strategy_weights(intent, user_profile, strategy_tags)
        trace.append(
            AgentTraceStep(
                step="build_strategy_weights",
                label="生成偏好权重",
                status="done",
                details={
                    "weights": strategy_weights.model_dump(),
                    "strategy_tags": [tag.model_dump() for tag in strategy_tags],
                },
            )
        )
        await emit_pending_trace()
        logger.info(
            "step done session_id=%s step=build_strategy_weights weights=%s",
            request.session_id,
            strategy_weights.model_dump(),
        )

        # ── Demo Mock 拦截：触发词命中时直接返回预设路线，绕过真实 POI 搜索 ─────────────────
        # 触发条件：消息或上轮消息中含有 demo 触发词（聚餐/餐厅/吃饭等）
        # 且 intent.city == 北京 且 intent.target_district 有值（已完成追问）
        _demo_source_msg = request.message or ""
        # 从 recent_messages 找上一轮用户消息（角色为 user 的最后一条，不含当前轮）
        _last_msg = next(
            (m.content for m in reversed(session_state.recent_messages) if m.role == "user"),
            "",
        ) if session_state and session_state.recent_messages else ""
        _demo_district = intent.target_district or request.target_district
        _demo_city = intent.city or request.city or "北京"
        if (
            (is_demo_trigger(_demo_source_msg) or is_demo_trigger(_last_msg))
            and _demo_city == "北京"
            and _demo_district
        ):
            logger.info("demo_mock session_id=%s district=%s", request.session_id, _demo_district)
            mock_routes = build_mock_routes(_demo_district)
            full_trace = build_mock_trace(
                _demo_source_msg or _last_msg,
                district=_demo_district,
                city=_demo_city,
                people_count=intent.people_count or 6,
            )
            # 流式逐步推送 trace（带延迟，约 10s 完成），路线在 generate_routes 步骤后推送
            await stream_mock_trace(
                steps=full_trace,
                emit=progress_callback,
                routes_at_step="generate_routes",
                routes=mock_routes,
                emit_routes=routes_callback,
            )
            reply = (
                f"好的！根据你在**{_demo_city}{_demo_district}**附近的需求，"
                f"我为你规划了 {len(mock_routes)} 条适合 {intent.people_count or 6} 人聚餐的路线，"
                f"从轻松老字号到精致宴请都有覆盖，你看哪条更符合心意？"
            )
            self.memory.save_turn_result(
                session_id=request.session_id,
                user_message=request.message,
                assistant_message=reply,
                intent=intent,
                user_profile=user_profile,
                routes=mock_routes,
                trip_state=trip_state,
            )
            return ChatResponse(
                session_id=request.session_id,
                message=reply,
                need_clarification=False,
                clarifying_question=None,
                intent=intent,
                user_profile=user_profile,
                routes=mock_routes,
                agent_trace=full_trace,
            )
        # ── Demo Mock 拦截结束 ──────────────────────────────────────────────────────

        pois = self.poi_service.search(intent, user_profile=user_profile, strategy_tags=strategy_tags)
        trace.append(
            AgentTraceStep(
                step="search_pois",
                label=f"召回 {len(pois)} 个候选 POI",
                status="done",
                details={
                    "count": len(pois),
                    "city": intent.city,
                    "names": [poi.name for poi in pois[:5]],
                    "strategy_tags": [tag.model_dump() for tag in strategy_tags],
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
        if not pois:
            message = self._no_poi_data_message(intent)
            trace.append(
                AgentTraceStep(
                    step="no_poi_data",
                    label="当前城市或区域没有可用 POI 数据",
                    status="fallback",
                    details={
                        "city": intent.city,
                        "target_district": intent.target_district,
                        "target_business_area": intent.target_business_area,
                    },
                )
            )
            await emit_pending_trace()
            self.memory.save_turn_result(
                session_id=request.session_id,
                user_message=request.message,
                assistant_message=message,
                intent=intent,
                user_profile=user_profile,
                routes=[],
                trip_state=trip_state,
            )
            return ChatResponse(
                session_id=request.session_id,
                message=message,
                need_clarification=False,
                clarifying_question=None,
                intent=intent,
                user_profile=user_profile,
                routes=[],
                agent_trace=trace,
            )
        expanded_recall = False
        relaxed_min_stops = False
        final_pois = pois

        async def build_routes(candidate_pois, allow_min_stops_fallback: bool) -> list[Route]:
            scores, fine_rank_details = self.fine_rank_service.score_map(
                candidate_pois,
                intent,
                user_profile,
                strategy_tags=strategy_tags,
                objective="balanced",
            )
            route_request = RoutePlanRequest(
                intent=intent,
                user_profile=user_profile,
                strategy_weights=strategy_weights,
                strategy_tags=strategy_tags,
                candidate_pois=candidate_pois,
                poi_relevance_scores=scores,
                poi_fine_rank_details=fine_rank_details,
            )
            response = await asyncio.to_thread(
                self.route_service.generate_routes,
                route_request,
                None,
                None,
                allow_min_stops_fallback,
            )
            return response.routes

        routes = await build_routes(pois, allow_min_stops_fallback=False)
        for recall_limit in [64, 80]:
            if len(routes) >= 3:
                break
            expanded_recall = True
            expanded_pois = self.poi_service.search(
                intent,
                user_profile=user_profile,
                strategy_tags=strategy_tags,
                limit=recall_limit,
                relax_preferences=True,
            )
            expanded_routes = await build_routes(expanded_pois, allow_min_stops_fallback=False)
            if len(expanded_routes) > len(routes):
                routes = expanded_routes
                final_pois = expanded_pois

        if len(routes) < 3:
            relaxed_routes = await build_routes(final_pois, allow_min_stops_fallback=True)
            if len(relaxed_routes) > len(routes):
                routes = relaxed_routes
                relaxed_min_stops = any(len(route.stops) == 2 for route in routes)

        if routes:
            await emit_routes(routes)
        trace.append(AgentTraceStep(step="generate_routes", label="生成多目标路线", status="done"))
        trace[-1].details = {
            "count": len(routes),
            "route_titles": [route.title for route in routes[:5]],
            "objectives": [route.objective for route in routes[:5]],
            "cross_route_dedup": True,
            "cross_route_poi_dedup": True,
            "expanded_recall": expanded_recall,
            "final_candidate_poi_count": len(final_pois),
            "relaxed_min_stops_to_2": relaxed_min_stops,
            "min_stop_counts": [len(route.stops) for route in routes[:5]],
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

    def _min_distance_to_pois(self, lat: float, lng: float, pois: list[POI]) -> float | None:
        """计算给定坐标到 POI 列表中最近一个的距离（km），无 POI 时返回 None。"""
        if not pois:
            return None
        min_dist = float("inf")
        for poi in pois:
            dlat = math.radians(poi.lat - lat)
            dlng = math.radians(poi.lng - lng)
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(math.radians(lat)) * math.cos(math.radians(poi.lat)) * math.sin(dlng / 2) ** 2
            )
            dist = 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist < min_dist:
                min_dist = dist
        return min_dist if min_dist != float("inf") else None

    def _apply_default_city_start(self, intent: Intent) -> tuple[Intent, dict[str, object] | None]:
        if intent.start_lat is not None and intent.start_lng is not None:
            return intent, None
        default_start = self.DEFAULT_CITY_STARTS.get(intent.city)
        if default_start is None:
            return intent, None
        updated = intent.model_copy(
            update={
                "start_location_name": intent.start_location_name or default_start["name"],
                "start_lat": default_start["lat"],
                "start_lng": default_start["lng"],
            }
        )
        return updated, default_start

    def _is_structured_replan_request(self, request: ChatRequest, session_state) -> bool:
        return bool(
            session_state.current_routes
            and request.event_type in {"replace_poi", "avoid_poi", "queue_spike", "traffic_jam", "user_tired", "weather_change"}
        )

    def _handle_structured_replan(self, request: ChatRequest, session_state, trace: list[AgentTraceStep]) -> ChatResponse:
        selected_route_id = request.selected_route_id or self._default_route_id(session_state.current_routes)
        affected_poi_id = request.target_poi_id or self._default_replacement_target(session_state.current_routes, selected_route_id)
        event_payload = dict(request.event_payload)
        if affected_poi_id:
            event_payload.setdefault("affected_poi_id", affected_poi_id)
        if request.event_type == "replace_poi":
            event_payload.setdefault("force_replace", True)

        trace.append(
            AgentTraceStep(
                step="local_replan",
                label="局部替换 POI" if request.event_type == "replace_poi" else "局部重规划",
                status="done",
                details={
                    "event_type": request.event_type,
                    "selected_route_id": selected_route_id,
                    "affected_poi_id": affected_poi_id,
                },
            )
        )
        response = self.replan_service.replan(
            ReplanRequest(
                session_id=request.session_id,
                selected_route_id=selected_route_id,
                event_type=request.event_type,
                event_label=request.message or "局部调整",
                current_routes=session_state.current_routes,
                current_lat=request.current_lat,
                current_lng=request.current_lng,
                current_time=request.event_payload.get("current_time"),
                event_payload=event_payload,
                intent=session_state.last_intent,
                user_profile=session_state.user_profile,
            )
        )
        routes = response.routes
        message = self._build_replan_message(routes, selected_route_id)
        self.memory.save_turn_result(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=message,
            intent=session_state.last_intent or Intent(),
            user_profile=session_state.user_profile or self.profile_service.get_profile(request.user_id, request),
            routes=routes,
            trip_state=session_state.trip_state,
        )
        return ChatResponse(
            session_id=request.session_id,
            message=message,
            need_clarification=False,
            clarifying_question=None,
            intent=session_state.last_intent,
            user_profile=session_state.user_profile,
            routes=routes,
            agent_trace=trace,
        )

    def _default_route_id(self, routes: list[Route]) -> str | None:
        return routes[0].route_id if routes else None

    def _default_replacement_target(self, routes: list[Route], selected_route_id: str | None) -> str | None:
        route = next((candidate for candidate in routes if candidate.route_id == selected_route_id), routes[0] if routes else None)
        if route is None or not route.stops:
            return None
        replaceable = route.stops[1:] or route.stops
        target = max(
            replaceable,
            key=lambda stop: (
                stop.queue_minutes,
                1 if stop.walking_intensity == "high" else 0,
                stop.estimated_cost,
            ),
        )
        return target.poi_id

    def _build_replan_message(self, routes: list[Route], selected_route_id: str | None) -> str:
        route = next((candidate for candidate in routes if candidate.route_id == selected_route_id), routes[0] if routes else None)
        if route is None:
            return "当前没有可调整的路线，我需要先生成一条路线再帮你换一家。"
        if route.changed_stops:
            change = route.changed_stops[0]
            return f"已在当前路线里把「{change.from_name}」换成「{change.to_name}」，并重新计算了后续交通、排队和评分。"
        return route.replan_reason or "已复核当前路线，暂时没有找到更合适的替代点。"

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
            "planning_mode": message_route.planning_mode.value if message_route.planning_mode else None,
            "candidate_planning_modes": [mode.value for mode in message_route.candidate_planning_modes],
            "inherit_previous": message_route.inherit_previous,
            "preserve_scenario": message_route.preserve_scenario,
            "references_previous_route": message_route.references_previous_route,
            "question_type": message_route.detail_type,
            "confidence": round(message_route.confidence, 2),
            "raw_confidence": message_route.raw_confidence,
            "confidence_source": message_route.confidence_source,
            "confidence_reasons": message_route.confidence_reasons,
            "reason": message_route.reason,
            "evidence": message_route.evidence,
        }

    def _handle_partial_replan(
        self,
        request: ChatRequest,
        session_state,
        trace: list[AgentTraceStep],
    ) -> ChatResponse | None:
        parsed_event = self.replan_intent_parser.parse(request.message, session_state.current_routes)
        if parsed_event is None:
            return None

        intent = session_state.last_intent or Intent()
        user_profile = session_state.user_profile or self.profile_service.get_profile(request.user_id, request)
        trip_state = session_state.trip_state or TripState.from_intent(intent)
        replan_request = ReplanRequest(
            session_id=request.session_id,
            event_type=parsed_event.event_type,
            event_label=parsed_event.event_label,
            current_routes=session_state.current_routes,
            selected_route_id=parsed_event.selected_route_id,
            current_poi_id=parsed_event.current_poi_id,
            locked_poi_ids=trip_state.locked_stop_ids,
            event_payload=parsed_event.event_payload,
            intent=intent,
            user_profile=user_profile,
        )
        replan_response = self.replan_service.replan(replan_request)
        message = self._format_partial_replan_message(replan_response.routes)
        trace.append(
            AgentTraceStep(
                step="partial_replan",
                label="基于原方案局部重规划",
                status="done",
                details={
                    "event_type": parsed_event.event_type,
                    "event_label": parsed_event.event_label,
                    "selected_route_id": parsed_event.selected_route_id,
                    "current_poi_id": parsed_event.current_poi_id,
                },
            )
        )
        self.memory.save_turn_result(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=message,
            intent=intent,
            user_profile=user_profile,
            routes=replan_response.routes,
            trip_state=trip_state,
        )
        return ChatResponse(
            session_id=request.session_id,
            message=message,
            need_clarification=False,
            clarifying_question=None,
            intent=intent,
            user_profile=user_profile,
            routes=replan_response.routes,
            agent_trace=trace,
        )

    def _handle_clarification(
        self,
        request: ChatRequest,
        session_state,
        trace: list[AgentTraceStep],
        decision: ClarificationDecision,
        intent: Intent | None = None,
    ) -> ChatResponse:
        trace.append(
            AgentTraceStep(
                step="clarify_intent",
                label="需要澄清用户需求",
                status="done",
                details=decision.model_dump(),
            )
        )
        message = decision.question
        # 追问计数 +1，确保下一轮不再追问
        session_state.clarification_count = getattr(session_state, "clarification_count", 0) + 1
        self.memory.save_turn_result(
            session_id=request.session_id,
            user_message=request.message,
            assistant_message=message,
            intent=intent or session_state.last_intent,
            user_profile=session_state.user_profile,
            routes=session_state.current_routes,
            trip_state=session_state.trip_state,
            clarification_count=session_state.clarification_count,
        )
        return ChatResponse(
            session_id=request.session_id,
            message=message,
            need_clarification=True,
            clarifying_question=message,
            clarification_type=decision.clarification_type,
            clarification_groups=decision.clarification_groups,
            inferred_context=decision.inferred_context,
            intent=intent,
            user_profile=session_state.user_profile,
            routes=session_state.current_routes,
            agent_trace=trace,
        )

    def _format_partial_replan_message(self, routes: list[Route]) -> str:
        if not routes:
            return "我尝试基于原方案做局部重规划，但当前没有可调整的路线。"
        route = routes[0]
        reason = route.replan_reason or "已基于原方案完成局部重规划。"
        changes = [f"{change.from_name or change.from_poi_id}换成{change.to_name or change.to_poi_id}" for change in route.changed_stops]
        warning_text = "；".join(route.live_warnings[:2])
        parts = [reason]
        if changes:
            parts.append("调整：" + "、".join(changes))
        if warning_text:
            parts.append("提醒：" + warning_text)
        parts.append(f"当前路线人均约 {route.total_cost_per_person} 元，排队约 {route.total_queue_minutes} 分钟。")
        return "\n".join(parts)

    def _profile_for_turn(self, request: ChatRequest, session_state, intent: Intent):
        has_request_profile = self.profile_service._request_has_profile_fields(request)
        if session_state.user_profile and not has_request_profile:
            base_profile = session_state.user_profile
        else:
            base_profile = self.profile_service.get_profile(request.user_id, request)
        return self.profile_service.update_from_chat(base_profile, intent, message=request.message)

    def _intent_type_label(self, intent_type: str) -> str:
        return {
            "new_plan": "新规划",
            "modify_plan": "修改已有路线",
            "replan": "局部重规划",
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
            "target_district": intent.target_district,
            "target_business_area": intent.target_business_area,
            "interest_tags": intent.interest_tags,
            "optimization_goals": intent.optimization_goals,
            "preferences": intent.preferences,
            "avoid_tags": intent.avoid_tags,
            "scenario": intent.scenario,
        }

    def _no_poi_data_message(self, intent: Intent) -> str:
        region = intent.target_business_area or intent.target_district
        if region:
            return f"当前在{intent.city}{region}还没有可用 POI 数据，可以换一个城市或区域，我再继续帮你规划。"
        return f"当前还没有{intent.city}的可用 POI 数据，可以换一个城市，我再继续帮你规划。"

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
            delta = self._normalize_intent_delta(delta, message, session_state)
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
                "added_preferences": "array using canonical labels; compatibility field, may include interest tags or optimization goals",
                "removed_preferences": "array using canonical labels; compatibility field, may include interest tags or optimization goals",
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
                    "content": STATE_DELTA_SYSTEM_PROMPT,
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

    def _normalize_intent_delta(self, delta: IntentDelta, message: str = "", session_state=None) -> IntentDelta:
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
        data = self._guard_relative_budget_change(data, message, session_state)
        normalized = IntentDelta.model_validate(data)
        return normalize_delta_units(normalized, message) if message else normalized

    def _guard_relative_budget_change(self, data: dict, message: str, session_state=None) -> dict:
        if not message or "budget_per_person" not in (data["added_hard_constraints"] | data["modified_hard_constraints"]):
            return data

        explicit_fields = extract_standard_unit_fields(message) | extract_explicit_trip_fields(message)
        if "budget_per_person" in explicit_fields:
            return data

        data["added_hard_constraints"].pop("budget_per_person", None)
        data["modified_hard_constraints"].pop("budget_per_person", None)
        if self._message_requests_lower_budget(message) and "省钱" not in data["added_preferences"]:
            data["added_preferences"].append("省钱")
        return data

    def _message_requests_lower_budget(self, message: str) -> bool:
        terms = ["降低人均消费", "降低消费", "降低预算", "省钱", "便宜", "预算低", "人均低", "少花", "花少点"]
        return any(term in message for term in terms)

    def _delta_allowed_values(self) -> dict[str, list[str]]:
        return {
            "preferences": ["美食", "咖啡", "拍照", "citywalk", "艺术展", "自然风景", "本地感", "夜景", "亲子", "室内", "安静", "少排队", "省钱", "少走路", "高性价比", "轻松", "时间紧", "朋友同行"],
            "avoid_tags": ["人流密集", "排队久", "太贵", "需要预约", "商业街", "拍照打卡", "辣", "步行多"],
            "needs": ["meal_stop", "rest_stop"],
            "hard_constraints": [
                "city",
                "people_count",
                "target_district",
                "target_business_area",
                "start_time",
                "duration_hours",
                "budget_per_person",
                "scenario",
            ],
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
            elif key in {"city", "target_district", "target_business_area", "start_time", "scenario"} and value:
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
        return is_add_constraint and ("美食" in added_preferences or any(term in message for term in meal_terms))

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
            # 只给 LLM 发精简摘要，避免 token 过多拖慢推理
            intent_summary = {
                k: v for k, v in {
                    "city": intent.city,
                    "start_time": intent.start_time,
                    "duration_hours": intent.duration_hours,
                    "people_count": intent.people_count,
                    "budget_per_person": intent.budget_per_person,
                    "interest_tags": intent.interest_tags,
                    "scenario": intent.scenario,
                }.items() if v
            }
            summary_input = {
                "intent": intent_summary,
                "routes": [
                    {
                        "title": route.title,
                        "summary": route.summary,
                        "total_cost_per_person": route.total_cost_per_person,
                        "total_distance_km": route.total_distance_km,
                        "total_travel_minutes": route.total_travel_minutes,
                        "total_queue_minutes": route.total_queue_minutes,
                        "stops": [
                            {
                                "name": stop.name,
                                "start_time": stop.start_time,
                                "end_time": stop.end_time,
                                "estimated_cost": stop.estimated_cost,
                                "transport_mode_from_previous": stop.transport_mode_from_previous,
                                "travel_minutes_from_previous": stop.travel_minutes_from_previous,
                                "highlight_text": stop.highlight_text,
                                "ugc_tip": stop.ugc_tip,
                                "reason": stop.reason,
                            }
                            for stop in route.stops
                        ],
                    }
                    for route in routes[:3]
                ],
            }
            logger.info("summarize_routes input=%s", self._preview(json.dumps(summary_input, ensure_ascii=False)))
            response = await self.llm_client.complete(
                [
                    {
                        "role": "system",
                        "content": ROUTE_SUMMARY_SYSTEM_PROMPT,
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
                        "content": DIRECT_CHAT_SYSTEM_PROMPT,
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

    def _gps_city_from_request(self, request: "ChatRequest | None") -> str:
        """从 request GPS 坐标推断城市名，无坐标/无匹配时返回空字符串。"""
        if not request:
            return ""
        lat = request.current_lat or request.start_lat
        lng = request.current_lng or request.start_lng
        if lat and lng:
            return self.clarification_policy._coords_to_city(lat, lng)
        return ""

    async def _llm_parse_intent_safe(self, message: str, request: "ChatRequest | None" = None) -> Intent | None:
        """并行预取时使用：LLM 解析意图，失败返回 None（不写 trace）。"""
        try:
            intent = await self._llm_parse_intent(message)
            gps_city = self._gps_city_from_request(request)
            if gps_city and not intent.city_from_message:
                intent = intent.model_copy(update={"city": gps_city})
            return intent
        except Exception as exc:
            logger.warning("prefetch parse_intent failed error=%s", type(exc).__name__)
            return None

    async def _parse_intent(
        self,
        message: str,
        trace: list[AgentTraceStep],
        request: "ChatRequest | None" = None,
        prefetched: "Intent | None" = None,
    ) -> Intent:
        gps_city = self._gps_city_from_request(request)

        # 有预取结果时直接使用，省去一次串行 LLM 调用
        if prefetched is not None:
            trace.append(
                AgentTraceStep(
                    step="parse_intent",
                    label="LLM 解析用户意图（并行预取）",
                    status="done",
                    details=self._intent_trace_details(prefetched),
                )
            )
            logger.info("step done step=parse_intent mode=llm_prefetch")
            return prefetched

        try:
            logger.info("step start step=parse_intent mode=llm")
            intent = await self._llm_parse_intent(message)
            # 如果 LLM 只是猜的城市（city_from_message=False），且 GPS 推断出了城市，则用 GPS 城市覆盖
            if gps_city and not intent.city_from_message:
                intent = intent.model_copy(update={"city": gps_city})
                logger.info("intent gps_city_override city=%s", gps_city)
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
            # fallback 时同样用 GPS 城市覆盖默认上海
            if gps_city:
                intent = intent.model_copy(update={"city": gps_city})
                logger.info("intent fallback gps_city_override city=%s", gps_city)
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
            "city": "string, 如果消息中有地名/城市/景点可推断则填写，否则返回空字符串（不要猜测默认值）",
            "people_count": "integer",
            "start_time": "HH:MM string",
            "duration_hours": "integer",
            "budget_per_person": "integer, CNY",
            "start_location_name": "string or null, route start place name when mentioned",
            "target_district": "string or null, destination district/area such as 徐汇区 or 朝阳区 when mentioned",
            "target_business_area": "string or null, destination business area/street such as 武康路 or 三里屯 when mentioned",
            "start_lat": "number or null, route start latitude when known",
            "start_lng": "number or null, route start longitude when known",
            "interest_tags": "array, experience tags only: 美食/咖啡/拍照/citywalk/艺术展/自然风景/本地感/夜景/亲子/室内/安静",
            "optimization_goals": "array, route optimization goals only: 少排队/省钱/少走路/高性价比/轻松/时间紧",
            "preferences": "array, compatibility field; can be empty or interest_tags + optimization_goals",
            "avoid_tags": "array, avoid items: 人流密集/排队久/太贵/需要预约/商业街/拍照打卡/步行多/辣",
            "scenario": "short snake_case string",
            "need_clarification": "boolean",
            "city_from_message": "boolean, true only if city can be clearly inferred from the message content or context (e.g. user mentioned a place, landmark, or city name); false if city is just a default guess",
        }
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": build_intent_parser_system_prompt(),
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

        for key in ("preferences", "interest_tags", "optimization_goals", "avoid_tags"):
            normalized[key] = self._coerce_string_list(normalized.get(key))

        for key in ("start_location_name", "target_district", "target_business_area"):
            value = normalized.get(key)
            normalized[key] = str(value).strip() if value else None

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
            preferences.append("美食")
        if any(term in message for term in ["少排队", "别排队", "不排队", "不想排队"]):
            preferences.append("少排队")
        if any(term in message for term in ["拍照", "出片", "打卡", "citywalk", "街区"]):
            preferences.append("拍照")
        if any(term in message for term in ["少走路", "轻松", "别太累", "不要太累"]):
            preferences.append("少走路")
        if "省钱" in message or "便宜" in message:
            preferences.append("省钱")
        if "亲子" in message or "小孩" in message:
            preferences.append("亲子")

        avoid_tags = []
        if any(term in message for term in ["人多", "拥挤", "人流密集"]):
            avoid_tags.append("人流密集")
        if any(term in message for term in ["排队久", "排队太久"]):
            avoid_tags.append("排队久")
        if any(term in message for term in ["太贵", "贵"]):
            avoid_tags.append("太贵")

        return Intent(
            city="",
            people_count=3 if "三" in message or "3" in message else 2,
            start_time="14:00",
            duration_hours=6,
            budget_per_person=300,
            target_district=self._extract_region_from_message(message, "district"),
            target_business_area=self._extract_region_from_message(message, "business_area"),
            preferences=preferences,
            avoid_tags=avoid_tags,
            scenario="friends_citywalk",
            need_clarification=False,
        )

    def _extract_region_from_message(self, message: str, kind: str) -> str | None:
        if kind == "district":
            match = re.search(r"[\u4e00-\u9fa5]{2,6}区|[\u4e00-\u9fa5]{2,6}县|[\u4e00-\u9fa5]{2,6}新区", message)
            return match.group(0) if match else None
        for area in ["武康路", "安福路", "外滩", "陆家嘴", "南京路", "淮海路", "新天地", "田子坊", "三里屯", "王府井", "后海", "什刹海", "南锣鼓巷", "国贸", "西单"]:
            if area in message:
                return area
        match = re.search(r"[\u4e00-\u9fa5]{2,8}(?:路|街|巷|弄|大道|步行街|老街)", message)
        return match.group(0) if match else None
