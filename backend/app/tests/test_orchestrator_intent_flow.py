import unittest
import json
from unittest.mock import AsyncMock

from app.agent.intent_enhancer import enhance_intent_from_message
from app.agent.message_router import MessageIntentType, MessageRoute
from app.agent.orchestrator import AgentOrchestrator
from app.schemas.chat import ChatRequest
from app.schemas.route import Route, RouteScoreBreakdown, RouteStop


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
            self.assertEqual(state.recent_messages[0].role, "user")
            self.assertEqual(state.recent_messages[-1].content, "已生成上海一日游路线。")

        import asyncio

        asyncio.run(run_case())

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

    def test_second_turn_adjustment_inherits_previous_intent(self) -> None:
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
            self.assertIn("更省钱", state.last_intent.preferences)
            self.assertIn("少排队", state.last_intent.preferences)
            self.assertIn("排队久", state.last_intent.avoid_tags)

        import asyncio

        asyncio.run(run_case())

    def test_adjustment_keeps_previous_city_over_onboarding_city(self) -> None:
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
            self.assertIn("更省钱", state.last_intent.preferences)
            self.assertIn("少排队", state.last_intent.preferences)
            self.assertIn("少走路", state.last_intent.preferences)
            self.assertIn("安静", state.last_intent.preferences)
            self.assertIn("排队久", state.last_intent.avoid_tags)
            self.assertIn("步行多", state.last_intent.avoid_tags)

        import asyncio

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
