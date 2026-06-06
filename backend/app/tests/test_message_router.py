import asyncio
import unittest
from unittest.mock import AsyncMock

from app.agent.message_router import MessageIntentType, MessageRouter, PlanningMode, TurnType
from app.agent.schemas import SessionState
from app.schemas.intent import Intent


class MessageRouterTest(unittest.TestCase):
    def test_llm_router_classifies_route_detail_question(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"intent_type":"route_detail_question","confidence":0.91,"references_previous_route":true,"detail_type":"transport_between_stops"}'
                            }
                        }
                    ]
                }
            )

            result = await MessageRouter(llm_client).classify(
                "就你刚刚生成的方案，那俩地之间怎么过去",
                SessionState(session_id="s1"),
            )

            self.assertEqual(result.intent_type, MessageIntentType.ROUTE_DETAIL_QUESTION)
            self.assertTrue(result.references_previous_route)
            self.assertEqual(result.detail_type, "transport_between_stops")

        asyncio.run(run_case())

    def test_router_falls_back_to_route_detail_when_llm_fails(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))

            result = await MessageRouter(llm_client).classify(
                "两个地点之间我怎么过去",
                SessionState(session_id="s1"),
            )

            self.assertEqual(result.intent_type, MessageIntentType.ROUTE_DETAIL_QUESTION)
            self.assertTrue(result.references_previous_route)

        asyncio.run(run_case())

    def test_router_falls_back_to_new_plan_for_outdoor_walk_recommendation(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))

            result = await MessageRouter(llm_client).classify(
                "今天天气好，适合户外漫步，有推荐吗",
                SessionState(session_id="s1"),
            )

            self.assertEqual(result.intent_type, MessageIntentType.NEW_PLAN)
            self.assertEqual(result.planning_mode, PlanningMode.NEW_PLAN)
            self.assertEqual(result.turn_type, TurnType.NEW_PLAN)

        asyncio.run(run_case())

    def test_router_recovers_when_llm_misclassifies_recommendation_as_general_chat(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"intent_type":"general_chat","turn_type":"general_chat","planning_mode":"general_chat","confidence":0.86,"reason":"not_route_related"}'
                            }
                        }
                    ]
                }
            )

            result = await MessageRouter(llm_client).classify(
                "今天天气好，适合户外漫步，有推荐吗",
                SessionState(session_id="s1"),
            )

            self.assertEqual(result.intent_type, MessageIntentType.NEW_PLAN)
            self.assertEqual(result.planning_mode, PlanningMode.NEW_PLAN)
            self.assertGreaterEqual(result.confidence, 0.65)

        asyncio.run(run_case())

    def test_router_falls_back_to_add_constraint_for_followup_food_request(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))
            state = SessionState(session_id="s1", last_intent=Intent(city="上海", preferences=["拍照"]))

            result = await MessageRouter(llm_client).classify("我还要吃饭", state)

            self.assertEqual(result.intent_type, MessageIntentType.MODIFY_PLAN)
            self.assertEqual(result.turn_type, TurnType.ADD_CONSTRAINT)
            self.assertTrue(result.inherit_previous)
            self.assertTrue(result.preserve_scenario)

        asyncio.run(run_case())

    def test_router_falls_back_to_full_replan_for_global_preference_change(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))
            state = SessionState(session_id="s1", last_intent=Intent(city="上海", preferences=["拍照"]))

            cheap_result = await MessageRouter(llm_client).classify("更省钱一点", state)
            queue_result = await MessageRouter(llm_client).classify("少排队一点", state)

            self.assertEqual(cheap_result.intent_type, MessageIntentType.MODIFY_PLAN)
            self.assertEqual(cheap_result.planning_mode, PlanningMode.FULL_REPLAN)
            self.assertTrue(cheap_result.inherit_previous)
            self.assertTrue(cheap_result.preserve_scenario)
            self.assertEqual(queue_result.planning_mode, PlanningMode.FULL_REPLAN)

        asyncio.run(run_case())

    def test_router_falls_back_to_partial_replan_for_local_or_live_route_changes(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))
            state = SessionState(session_id="s1", last_intent=Intent(city="上海", preferences=["拍照"]))

            for message in ["换一家", "不喜欢这家店，换一家", "下雨了怎么办", "路上临时堵车了"]:
                with self.subTest(message=message):
                    result = await MessageRouter(llm_client).classify(message, state)

                    self.assertEqual(result.intent_type, MessageIntentType.REPLAN)
                    self.assertEqual(result.planning_mode, PlanningMode.PARTIAL_REPLAN)
                    self.assertTrue(result.inherit_previous)
                    self.assertTrue(result.references_previous_route)

        asyncio.run(run_case())

    def test_router_marks_ambiguous_replan_mode_candidates(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))
            state = SessionState(session_id="s1", last_intent=Intent(city="上海", preferences=["拍照"]))

            result = await MessageRouter(llm_client).classify("换个便宜点的", state)

            self.assertLess(result.confidence, 0.5)
            self.assertEqual(result.planning_mode, PlanningMode.FULL_REPLAN)
            self.assertEqual(result.candidate_planning_modes, [PlanningMode.FULL_REPLAN, PlanningMode.PARTIAL_REPLAN])

        asyncio.run(run_case())

    def test_explicit_full_replan_does_not_keep_ambiguous_candidates_from_llm(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"intent_type":"modify_plan","turn_type":"modify_constraint",'
                                    '"planning_mode":"full_replan",'
                                    '"candidate_planning_modes":["full_replan","partial_replan"],'
                                    '"confidence":0.42,"inherit_previous":true,'
                                    '"references_previous_route":true,"preserve_scenario":true}'
                                )
                            }
                        }
                    ]
                }
            )
            state = SessionState(session_id="s1", last_intent=Intent(city="上海", preferences=["网红打卡"]))

            result = await MessageRouter(llm_client).classify("重新生成路线", state)

            self.assertEqual(result.intent_type, MessageIntentType.MODIFY_PLAN)
            self.assertEqual(result.planning_mode, PlanningMode.FULL_REPLAN)
            self.assertEqual(result.candidate_planning_modes, [])
            self.assertGreaterEqual(result.confidence, 0.75)

        asyncio.run(run_case())

    def test_explicit_partial_replan_does_not_keep_ambiguous_candidates_from_llm(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"intent_type":"modify_plan","turn_type":"modify_constraint",'
                                    '"planning_mode":"full_replan",'
                                    '"candidate_planning_modes":["full_replan","partial_replan"],'
                                    '"confidence":0.42,"inherit_previous":true,'
                                    '"references_previous_route":true,"preserve_scenario":true}'
                                )
                            }
                        }
                    ]
                }
            )
            state = SessionState(session_id="s1", last_intent=Intent(city="上海", preferences=["网红打卡"]))

            result = await MessageRouter(llm_client).classify("只替换这个地点", state)

            self.assertEqual(result.intent_type, MessageIntentType.REPLAN)
            self.assertEqual(result.planning_mode, PlanningMode.PARTIAL_REPLAN)
            self.assertEqual(result.candidate_planning_modes, [])
            self.assertGreaterEqual(result.confidence, 0.75)

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
