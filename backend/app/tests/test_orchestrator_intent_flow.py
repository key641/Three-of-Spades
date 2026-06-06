import unittest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from app.agent.intent_enhancer import enhance_intent_from_message
from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode, TurnType
from app.agent.orchestrator import AgentOrchestrator
from app.agent.schemas import IntentDelta, QueryUnderstanding, TripState
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent
from app.schemas.route import Route, RoutePlanResponse, RouteScoreBreakdown, RouteStop
from app.schemas.user import UserProfile


def stub_route_planning_router(orchestrator: AgentOrchestrator) -> None:
    orchestrator.message_router.classify = AsyncMock(
        return_value=MessageRoute(intent_type=MessageIntentType.NEW_PLAN, confidence=1)
    )


def build_route() -> Route:
    return Route(
        route_id="route_balanced",
        title="综合最优路线",
        objective="balanced",
        summary="测试路线",
        total_duration_minutes=180,
        total_cost_per_person=120,
        total_queue_minutes=5,
        total_travel_minutes=18,
        total_distance_km=2.4,
        score=86,
        score_breakdown=RouteScoreBreakdown(quality=88, queue=90, budget=82, distance=85, preference=86),
        stops=[
            RouteStop(
                poi_id="p1",
                name="静安雕塑公园",
                category="park",
                start_time="09:00",
                end_time="10:00",
                estimated_cost=0,
                queue_minutes=0,
                tags=["安静"],
            ),
            RouteStop(
                poi_id="p2",
                name="外滩观景平台",
                category="scenic",
                district="黄浦区",
                address="中山东一路",
                start_time="10:18",
                end_time="11:00",
                estimated_cost=0,
                queue_minutes=5,
                tags=["拍照"],
                walking_intensity="low",
                highlight_text="适合看江景",
                ugc_tip="傍晚更出片",
                recommended_transport=["metro", "bike"],
                travel_minutes_from_previous=18,
                distance_km_from_previous=2.4,
                transport_mode_from_previous="metro/bike",
                reason="沿线交通方便",
            ),
        ],
        reasons=["测试"],
    )


class OrchestratorIntentFlowTest(unittest.TestCase):
    def test_relative_budget_request_does_not_raise_previous_budget_to_default(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            state = orchestrator.memory.get_state("s1")
            previous_intent = Intent(city="上海", budget_per_person=200, preferences=["拍照"])
            state.last_intent = previous_intent
            state.trip_state = TripState.from_intent(previous_intent)
            orchestrator.memory.save_state(state)
            orchestrator.llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"understanding":{"turn_type":"modify_constraint",'
                                    '"inherit_previous":true,"preserve_scenario":true,'
                                    '"confidence":0.86,"reason":"用户要求降低人均消费"},'
                                    '"delta":{"modified_hard_constraints":{"budget_per_person":300},'
                                    '"added_preferences":["更省钱"],"removed_preferences":[]}}'
                                )
                            }
                        }
                    ]
                }
            )

            _understanding, delta, _source = await orchestrator._parse_query_delta(
                "重新规划，降低人均消费",
                state,
                QueryUnderstanding(turn_type="modify_constraint", inherit_previous=True),
                IntentDelta(),
                [],
            )

            self.assertNotIn("budget_per_person", delta.modified_hard_constraints)
            self.assertIn("省钱", delta.added_preferences)

        import asyncio

        asyncio.run(run_case())

    def test_city_region_without_poi_data_returns_visible_no_data_message(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "city": "上海",
                                        "people_count": 2,
                                        "start_time": "14:00",
                                        "duration_hours": 4,
                                        "budget_per_person": 300,
                                        "target_district": "不存在区",
                                        "target_business_area": None,
                                        "start_location_name": None,
                                        "start_lat": None,
                                        "start_lng": None,
                                        "preferences": ["citywalk"],
                                        "interest_tags": ["citywalk"],
                                        "optimization_goals": [],
                                        "avoid_tags": [],
                                        "scenario": "friends_citywalk",
                                        "need_clarification": False,
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
            )

            response = await orchestrator.handle_message(ChatRequest(session_id="s1", message="上海不存在区 citywalk"))

            self.assertEqual(response.routes, [])
            self.assertIn("没有可用 POI 数据", response.message)
            self.assertIn("换一个城市", response.message)
            self.assertTrue(any(step.step == "no_poi_data" for step in response.agent_trace))

        asyncio.run(run_case())

    def test_explicit_budget_amount_can_change_previous_budget(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            state = orchestrator.memory.get_state("s1")
            previous_intent = Intent(city="上海", budget_per_person=200, preferences=["拍照"])
            state.last_intent = previous_intent
            state.trip_state = TripState.from_intent(previous_intent)
            orchestrator.memory.save_state(state)
            orchestrator.llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"understanding":{"turn_type":"modify_constraint",'
                                    '"inherit_previous":true,"preserve_scenario":true,'
                                    '"confidence":0.9,"reason":"用户明确给出新的人均预算"},'
                                    '"delta":{"modified_hard_constraints":{"budget_per_person":150},'
                                    '"added_preferences":["更省钱"],"removed_preferences":[]}}'
                                )
                            }
                        }
                    ]
                }
            )

            _understanding, delta, _source = await orchestrator._parse_query_delta(
                "重新规划，人均150以内",
                state,
                QueryUnderstanding(turn_type="modify_constraint", inherit_previous=True),
                IntentDelta(),
                [],
            )

            self.assertEqual(delta.modified_hard_constraints["budget_per_person"], 150)
            self.assertIn("省钱", delta.added_preferences)

        import asyncio

        asyncio.run(run_case())

    def test_fallback_intent_is_enhanced_by_message(self) -> None:
        orchestrator = AgentOrchestrator()
        fallback_intent = orchestrator._mock_parse_intent("想要在北京一日游")

        intent = enhance_intent_from_message(fallback_intent, "想要在北京一日游")

        self.assertEqual(intent.city, "北京")
        self.assertEqual(intent.duration_hours, 8)

    def test_handle_message_saves_structured_session_state(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海一日游路线。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想在上海一日游"))

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "上海")
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertEqual(state.last_intent.start_location_name, "静安寺站")
            self.assertEqual(state.last_intent.start_lat, 31.2231)
            self.assertEqual(state.last_intent.start_lng, 121.4466)
            self.assertEqual(state.recent_messages[0].role, "user")
            self.assertEqual(state.recent_messages[-1].content, "已生成上海一日游路线。")

        import asyncio

        asyncio.run(run_case())

    def test_default_city_start_is_added_for_beijing_without_overriding_explicit_start(self) -> None:
        orchestrator = AgentOrchestrator()

        beijing, default_start = orchestrator._apply_default_city_start(Intent(city="北京"))
        explicit, explicit_default = orchestrator._apply_default_city_start(
            Intent(city="北京", start_location_name="故宫", start_lat=39.9163, start_lng=116.3972)
        )

        self.assertEqual(default_start["name"], "西单站")
        self.assertEqual(beijing.start_location_name, "西单站")
        self.assertEqual(beijing.start_lat, 39.9072)
        self.assertEqual(beijing.start_lng, 116.3740)
        self.assertIsNone(explicit_default)
        self.assertEqual(explicit.start_location_name, "故宫")
        self.assertEqual(explicit.start_lat, 39.9163)
        self.assertEqual(explicit.start_lng, 116.3972)

    def test_route_detail_question_uses_saved_routes_without_replanning(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                return_value=MessageRoute(
                    intent_type=MessageIntentType.ROUTE_DETAIL_QUESTION,
                    confidence=1,
                    references_previous_route=True,
                    detail_type="transport_between_stops",
                )
            )
            orchestrator.route_service.generate_routes = AsyncMock()
            state = orchestrator.memory.get_state("s1")
            state.current_routes = [build_route()]
            orchestrator.memory.save_state(state)

            response = await orchestrator.handle_message(
                ChatRequest(session_id="s1", user_id="user_001", message="就你刚刚生成的方案，那俩地之间怎么过去")
            )

            self.assertIn("静安雕塑公园", response.message)
            self.assertIn("外滩观景平台", response.message)
            self.assertIn("地铁或骑行", response.message)
            orchestrator.route_service.generate_routes.assert_not_called()

        import asyncio

        asyncio.run(run_case())

    def test_structured_replace_poi_uses_local_replan_without_strategy_regeneration(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            route = build_route()
            updated = route.model_copy(deep=True)
            updated.changed_stops = []
            orchestrator.replan_service.replan = MagicMock(return_value=RoutePlanResponse(routes=[updated]))
            orchestrator.route_service.generate_routes = MagicMock()
            state = orchestrator.memory.get_state("s1")
            state.current_routes = [route]
            state.last_intent = Intent(city="上海", preferences=["拍照"])
            state.user_profile = UserProfile(user_id="user_001")
            orchestrator.memory.save_state(state)

            response = await orchestrator.handle_message(
                ChatRequest(
                    session_id="s1",
                    user_id="user_001",
                    message="帮我换一家",
                    event_type="replace_poi",
                    selected_route_id=route.route_id,
                    event_payload={"force_replace": True},
                )
            )

            orchestrator.replan_service.replan.assert_called_once()
            orchestrator.route_service.generate_routes.assert_not_called()
            self.assertEqual(response.agent_trace[0].step, "local_replan")
            self.assertEqual(response.agent_trace[0].label, "局部替换 POI")

        import asyncio

        asyncio.run(run_case())

    def test_partial_replan_uses_replan_service_without_full_regeneration(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                return_value=MessageRoute(
                    intent_type=MessageIntentType.REPLAN,
                    turn_type=TurnType.MODIFY_CONSTRAINT,
                    planning_mode=PlanningMode.PARTIAL_REPLAN,
                    confidence=1,
                    references_previous_route=True,
                    inherit_previous=True,
                    preserve_scenario=True,
                )
            )
            original_route = build_route()
            updated_route = original_route.model_copy(update={"replan_reason": "已局部替换受影响点位。"})
            orchestrator.replan_service.replan = unittest.mock.Mock(return_value=RoutePlanResponse(routes=[updated_route]))
            orchestrator.route_service.generate_routes = unittest.mock.Mock()
            state = orchestrator.memory.get_state("s1")
            state.last_intent = enhance_intent_from_message(orchestrator._mock_parse_intent("上海一日游"), "上海一日游")
            state.user_profile = UserProfile(user_id="user_001", preferences=["拍照"])
            state.current_routes = [original_route]
            orchestrator.memory.save_state(state)

            response = await orchestrator.handle_message(
                ChatRequest(session_id="s1", user_id="user_001", message="不喜欢这家店，换一家")
            )

            orchestrator.replan_service.replan.assert_called_once()
            orchestrator.route_service.generate_routes.assert_not_called()
            self.assertEqual(response.routes[0].replan_reason, "已局部替换受影响点位。")
            self.assertIn("局部", response.message)
            self.assertEqual(orchestrator.memory.get_state("s1").current_routes[0].replan_reason, "已局部替换受影响点位。")

        import asyncio

        asyncio.run(run_case())

    def test_missing_required_city_returns_clarification_without_planning(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                return_value=MessageRoute(
                    intent_type=MessageIntentType.NEW_PLAN,
                    turn_type=TurnType.NEW_PLAN,
                    planning_mode=PlanningMode.NEW_PLAN,
                    confidence=0.9,
                )
            )
            orchestrator.llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"city":"上海","people_count":1,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"preferences":["一日游"],"avoid_tags":[],"scenario":"city_day_trip","need_clarification":false,"city_from_message":false}'
                            }
                        }
                    ]
                }
            )
            orchestrator.route_service.generate_routes = unittest.mock.Mock()

            response = await orchestrator.handle_message(
                ChatRequest(session_id="s_missing_city", user_id="user_001", message="周末帮我安排一日游")
            )

            self.assertTrue(response.need_clarification)
            self.assertIn("城市", response.message)
            orchestrator.route_service.generate_routes.assert_not_called()
            self.assertTrue(any(step.step == "clarify_intent" for step in response.agent_trace))

        import asyncio

        asyncio.run(run_case())

    def test_low_confidence_between_replan_modes_asks_before_parsing_or_planning(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                return_value=MessageRoute(
                    intent_type=MessageIntentType.MODIFY_PLAN,
                    turn_type=TurnType.MODIFY_CONSTRAINT,
                    planning_mode=PlanningMode.FULL_REPLAN,
                    confidence=0.35,
                    references_previous_route=True,
                    inherit_previous=True,
                    candidate_planning_modes=[PlanningMode.FULL_REPLAN, PlanningMode.PARTIAL_REPLAN],
                )
            )
            orchestrator.llm_client.complete = AsyncMock()
            orchestrator.route_service.generate_routes = unittest.mock.Mock()
            state = orchestrator.memory.get_state("s_ambiguous")
            state.last_intent = enhance_intent_from_message(orchestrator._mock_parse_intent("上海一日游"), "上海一日游")
            state.current_routes = [build_route()]
            orchestrator.memory.save_state(state)

            response = await orchestrator.handle_message(
                ChatRequest(session_id="s_ambiguous", user_id="user_001", message="换个便宜点的")
            )

            self.assertTrue(response.need_clarification)
            self.assertIn("重新生成", response.message)
            self.assertIn("换掉", response.message)
            orchestrator.llm_client.complete.assert_not_called()
            orchestrator.route_service.generate_routes.assert_not_called()

        import asyncio

        asyncio.run(run_case())

    def test_empty_routes_summary_does_not_claim_routes_were_generated(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()

            message = await orchestrator._summarize_route_result(
                intent=enhance_intent_from_message(orchestrator._mock_parse_intent("北京一日游"), "北京一日游"),
                pois=[],
                routes=[],
                trace=[],
            )

            self.assertIn("北京", message)
            self.assertIn("候选点不足", message)
            self.assertNotIn("生成了几条可执行路线", message)

        import asyncio

        asyncio.run(run_case())

    def test_summarize_route_result_passes_new_route_fields_to_llm(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.llm_client.complete = AsyncMock(
                return_value={"choices": [{"message": {"content": "路线总结"}}]}
            )

            await orchestrator._summarize_route_result(
                intent=enhance_intent_from_message(orchestrator._mock_parse_intent("上海一日游"), "上海一日游"),
                pois=[],
                routes=[build_route()],
                trace=[],
            )

            messages = orchestrator.llm_client.complete.call_args.args[0]
            summary_input = json.loads(messages[1]["content"])
            route = summary_input["routes"][0]
            stop = route["stops"][1]
            self.assertEqual(route["total_travel_minutes"], 18)
            self.assertEqual(route["total_distance_km"], 2.4)
            self.assertEqual(stop["district"], "黄浦区")
            self.assertEqual(stop["address"], "中山东一路")
            self.assertEqual(stop["walking_intensity"], "low")
            self.assertEqual(stop["highlight_text"], "适合看江景")
            self.assertEqual(stop["ugc_tip"], "傍晚更出片")
            self.assertEqual(stop["recommended_transport"], ["metro", "bike"])
            self.assertEqual(stop["reason"], "沿线交通方便")

        import asyncio

        asyncio.run(run_case())

    def test_summarize_route_result_prompt_requires_visible_route_details(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.llm_client.complete = AsyncMock(
                return_value={"choices": [{"message": {"content": "route summary"}}]}
            )

            await orchestrator._summarize_route_result(
                intent=enhance_intent_from_message(orchestrator._mock_parse_intent("上海一日游"), "上海一日游"),
                pois=[],
                routes=[build_route()],
                trace=[],
            )

            messages = orchestrator.llm_client.complete.call_args.args[0]
            system_prompt = messages[0]["content"]
            for field in [
                "highlight_text",
                "ugc_tip",
                "reason",
                "transport_mode_from_previous",
                "distance_km_from_previous",
                "total_distance_km",
            ]:
                self.assertIn(field, system_prompt)

        import asyncio

        asyncio.run(run_case())

    def test_summarize_route_result_fallback_includes_route_details(self) -> None:
        async def run_case() -> None:
            route = build_route()
            orchestrator = AgentOrchestrator()
            orchestrator.llm_client.complete = AsyncMock(side_effect=RuntimeError("llm unavailable"))

            trace = []
            message = await orchestrator._summarize_route_result(
                intent=enhance_intent_from_message(orchestrator._mock_parse_intent("上海一日游"), "上海一日游"),
                pois=[],
                routes=[route],
                trace=trace,
            )

            self.assertIn("LLM", message)
            self.assertIn("不可用", message)
            self.assertIn(route.title, message)
            self.assertIn("2.4", message)
            self.assertIn("18", message)
            self.assertIn(route.stops[1].highlight_text, message)
            self.assertIn(route.stops[1].ugc_tip, message)
            self.assertIn(route.stops[1].reason, message)
            self.assertEqual(trace[-1].step, "summarize_routes")
            self.assertEqual(trace[-1].status, "fallback")

        import asyncio

        asyncio.run(run_case())

    def test_second_turn_adjustment_inherits_previous_intent(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.message_router.classify = AsyncMock(
                side_effect=[
                    MessageRoute(intent_type=MessageIntentType.NEW_PLAN, planning_mode=PlanningMode.NEW_PLAN, confidence=1),
                    MessageRoute(
                        intent_type=MessageIntentType.NEW_PLAN,
                        turn_type=TurnType.MODIFY_CONSTRAINT,
                        planning_mode=PlanningMode.NEW_PLAN,
                        inherit_previous=True,
                        preserve_scenario=True,
                        confidence=1,
                    ),
                ]
            )
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海一日游路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"14:00","duration_hours":6,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已按更省钱、少排队重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想在上海一日游"))
            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="预算低一点，别排队"))

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "上海")
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertIn("省钱", state.last_intent.preferences)
            self.assertIn("少排队", state.last_intent.preferences)
            self.assertIn("排队久", state.last_intent.avoid_tags)

        import asyncio

        asyncio.run(run_case())

    def test_adjustment_keeps_previous_city_over_onboarding_city(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.message_router.classify = AsyncMock(
                side_effect=[
                    MessageRoute(intent_type=MessageIntentType.NEW_PLAN, planning_mode=PlanningMode.NEW_PLAN, confidence=1),
                    MessageRoute(
                        intent_type=MessageIntentType.NEW_PLAN,
                        turn_type=TurnType.MODIFY_CONSTRAINT,
                        planning_mode=PlanningMode.NEW_PLAN,
                        inherit_previous=True,
                        preserve_scenario=True,
                        confidence=1,
                    ),
                ]
            )
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海一日游路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"14:00","duration_hours":6,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已按少排队重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想在上海一日游", city="北京"))
            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="不想排队", city="北京"))

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "上海")
            self.assertIn("少排队", state.last_intent.preferences)
            self.assertIn("排队久", state.last_intent.avoid_tags)

        import asyncio

        asyncio.run(run_case())

    def test_followup_without_city_keeps_previous_city_over_onboarding_city(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海一日游路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"14:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已按打车出行重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想在上海一日游", city="北京"))
            await orchestrator.handle_message(
                ChatRequest(
                    session_id="s1",
                    user_id="user_001",
                    message="你把刚刚的方案改一下，我想要一个打车出行的一日游方案",
                    city="北京",
                )
            )

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "上海")
            self.assertEqual(state.last_intent.duration_hours, 8)

        import asyncio

        asyncio.run(run_case())

    def test_add_food_followup_preserves_photo_citywalk_trip_context(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                side_effect=[
                    MessageRoute(intent_type=MessageIntentType.NEW_PLAN, turn_type=TurnType.NEW_PLAN, confidence=1),
                    MessageRoute(
                        intent_type=MessageIntentType.MODIFY_PLAN,
                        turn_type=TurnType.ADD_CONSTRAINT,
                        confidence=1,
                        inherit_previous=True,
                        preserve_scenario=True,
                    ),
                ]
            )
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["拍照"],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海拍照一日游路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"北京","people_count":1,"start_time":"14:00","duration_hours":4,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["吃好"],"avoid_tags":[],"scenario":"foodie_tour","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已加入吃饭节点重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想两个人在上海一日游，喜欢拍照"))
            response = await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我还要吃饭"))

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "上海")
            self.assertEqual(state.last_intent.people_count, 2)
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertEqual(state.last_intent.scenario, "friends_citywalk")
            self.assertEqual(state.last_intent.preferences, ["拍照", "美食"])
            self.assertIsNotNone(state.trip_state)
            self.assertEqual(state.trip_state.city, "上海")
            self.assertEqual(state.trip_state.people_count, 2)
            self.assertEqual(state.trip_state.duration_hours, 8)
            self.assertEqual(state.trip_state.soft_preferences, ["拍照", "美食"])
            self.assertIn("meal_stop", state.trip_state.must_include)
            route_step = next(step for step in response.agent_trace if step.step == "route_message")
            delta_step = next(step for step in response.agent_trace if step.step == "apply_query_delta")
            self.assertEqual(route_step.details["turn_type"], "add_constraint")
            self.assertTrue(route_step.details["inherit_previous"])
            self.assertIn("meal_stop", delta_step.details["added"])
            self.assertIn("保留", response.message)
            self.assertIn("上海", response.message)
            self.assertIn("2人", response.message)
            self.assertIn("拍照", response.message)
            self.assertIn("新增", response.message)
            self.assertIn("吃饭节点", response.message)

        import asyncio

        asyncio.run(run_case())

    def test_followup_explicit_people_and_negative_meal_override_previous_state(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                side_effect=[
                    MessageRoute(intent_type=MessageIntentType.NEW_PLAN, turn_type=TurnType.NEW_PLAN, confidence=1),
                    MessageRoute(
                        intent_type=MessageIntentType.MODIFY_PLAN,
                        turn_type=TurnType.ADD_CONSTRAINT,
                        confidence=1,
                        inherit_previous=True,
                        preserve_scenario=True,
                    ),
                ]
            )
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":1,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["网红打卡","吃好"],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海单人路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"14:00","duration_hours":4,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["吃饭","朋友同行"],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已按双人同行重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s2", user_id="user_001", message="我一个人在上海玩一天，想网红打卡和吃饭"))
            response = await orchestrator.handle_message(ChatRequest(session_id="s2", user_id="user_001", message="我不要吃饭，有朋友和我一起"))

            state = orchestrator.memory.get_state("s2")
            self.assertEqual(state.last_intent.people_count, 2)
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertIn("朋友同行", state.last_intent.preferences)
            self.assertNotIn("美食", state.last_intent.preferences)
            self.assertNotIn("吃饭", state.last_intent.preferences)
            self.assertNotIn("meal_stop", state.trip_state.must_include)
            self.assertNotIn("meal_stop", state.trip_state.implicit_needs)
            delta_step = next(step for step in response.agent_trace if step.step == "apply_query_delta")
            self.assertEqual(delta_step.details["changed"]["people_count"], {"from": 1, "to": 2})
            self.assertIn("meal_stop", delta_step.details["removed"])
            self.assertNotIn("meal_stop", delta_step.details["added"])
            self.assertIn("人数从1改为2", response.message)
            self.assertNotIn("新增了吃饭", response.message)
            self.assertIn("移除了", response.message)
            self.assertIn("吃饭节点", response.message)

        import asyncio

        asyncio.run(run_case())

    def test_followup_uses_llm_structured_delta_as_primary_state_update(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            orchestrator.message_router.classify = AsyncMock(
                side_effect=[
                    MessageRoute(intent_type=MessageIntentType.NEW_PLAN, turn_type=TurnType.NEW_PLAN, confidence=1),
                    MessageRoute(
                        intent_type=MessageIntentType.MODIFY_PLAN,
                        turn_type=TurnType.ADD_CONSTRAINT,
                        confidence=1,
                        inherit_previous=True,
                        preserve_scenario=True,
                    ),
                ]
            )
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":1,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["拍照","吃好"],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海双人路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":1,"start_time":"14:00","duration_hours":4,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["吃饭"],"avoid_tags":[],"scenario":"foodie_tour","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"understanding":{"turn_type":"add_constraint","inherit_previous":true,"preserve_scenario":true,"confidence":0.95,"reason":"明确说朋友同行且不吃饭"},"delta":{"modified_hard_constraints":{"people_count":2},"added_preferences":["朋友同行"],"removed_preferences":["吃好"],"removed_must_include":["meal_stop"],"removed_implicit_needs":["meal_stop"]}}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已按结构化 delta 重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s3", user_id="user_001", message="我一个人在上海玩一天，想拍照和吃饭"))
            response = await orchestrator.handle_message(ChatRequest(session_id="s3", user_id="user_001", message="我不要吃饭，有朋友和我一起"))

            state = orchestrator.memory.get_state("s3")
            self.assertEqual(state.last_intent.people_count, 2)
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertEqual(state.last_intent.preferences, ["拍照", "朋友同行"])
            self.assertNotIn("meal_stop", state.trip_state.must_include)
            delta_step = next(step for step in response.agent_trace if step.step == "apply_query_delta")
            self.assertEqual(delta_step.details["changed"]["people_count"], {"from": 1, "to": 2})
            self.assertEqual(delta_step.details["source"], "llm_structured_delta")

        import asyncio

        asyncio.run(run_case())

    def test_adjustment_with_message_city_switches_from_previous_and_onboarding_city(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":["少排队"],"avoid_tags":["排队久"],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海一日游路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"杭州","people_count":2,"start_time":"14:00","duration_hours":6,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已切换到杭州重新规划。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想在上海一日游", city="北京"))
            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="换成杭州吧", city="北京"))

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "杭州")
            self.assertTrue(state.last_intent.city_from_message)
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertIn("少排队", state.last_intent.preferences)
            self.assertIn("排队久", state.last_intent.avoid_tags)

        import asyncio

        asyncio.run(run_case())

    def test_third_turn_adjustment_accumulates_context(self) -> None:
        async def run_case() -> None:
            orchestrator = AgentOrchestrator()
            stub_route_planning_router(orchestrator)
            orchestrator.message_router.classify = AsyncMock(
                side_effect=[
                    MessageRoute(intent_type=MessageIntentType.NEW_PLAN, planning_mode=PlanningMode.NEW_PLAN, confidence=1),
                    MessageRoute(
                        intent_type=MessageIntentType.NEW_PLAN,
                        turn_type=TurnType.MODIFY_CONSTRAINT,
                        planning_mode=PlanningMode.NEW_PLAN,
                        inherit_previous=True,
                        preserve_scenario=True,
                        confidence=1,
                    ),
                    MessageRoute(
                        intent_type=MessageIntentType.NEW_PLAN,
                        turn_type=TurnType.ADD_CONSTRAINT,
                        planning_mode=PlanningMode.NEW_PLAN,
                        inherit_previous=True,
                        preserve_scenario=True,
                        confidence=1,
                    ),
                ]
            )
            orchestrator.llm_client.complete = AsyncMock(
                side_effect=[
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"09:00","duration_hours":8,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已生成上海一日游路线。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"14:00","duration_hours":6,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已按更省钱、少排队重新规划。"}}]},
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"city":"上海","people_count":2,"start_time":"14:00","duration_hours":6,"budget_per_person":300,"start_location_name":null,"start_lat":null,"start_lng":null,"preferences":[],"avoid_tags":[],"scenario":"friends_citywalk","need_clarification":false}'
                                }
                            }
                        ]
                    },
                    {"choices": [{"message": {"content": "已继续减少步行并优化安静点位。"}}]},
                ]
            )

            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="我想在上海一日游"))
            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="预算低一点，别排队"))
            await orchestrator.handle_message(ChatRequest(session_id="s1", user_id="user_001", message="再少走路一点，安静些"))

            state = orchestrator.memory.get_state("s1")
            self.assertEqual(state.last_intent.city, "上海")
            self.assertEqual(state.last_intent.duration_hours, 8)
            self.assertIn("省钱", state.last_intent.preferences)
            self.assertIn("少排队", state.last_intent.preferences)
            self.assertIn("少走路", state.last_intent.preferences)
            self.assertIn("安静", state.last_intent.preferences)
            self.assertIn("排队久", state.last_intent.avoid_tags)

        import asyncio

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
