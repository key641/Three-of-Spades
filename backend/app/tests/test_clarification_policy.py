import unittest

from app.agent.clarification_policy import ClarificationPolicy
from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode, TurnType
from app.agent.schemas import SessionState
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent


class ClarificationPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ClarificationPolicy()

    def test_new_plan_without_city_asks_for_city_instead_of_using_default(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="周末帮我安排一日游"),
            intent=Intent(city="上海", city_from_message=False, preferences=["一日游"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )

        self.assertTrue(decision.need_clarification)
        self.assertEqual(decision.clarification_type, "missing_required_field")
        self.assertEqual(decision.missing_field, "city")
        self.assertIn("城市", decision.question)

    def test_existing_context_city_prevents_repeated_city_clarification(self) -> None:
        state = SessionState(session_id="s1", last_intent=Intent(city="北京", city_from_message=True))

        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="少排队一点"),
            intent=Intent(city="北京", city_from_message=False, preferences=["少排队"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.MODIFY_CONSTRAINT,
                planning_mode=PlanningMode.FULL_REPLAN,
                confidence=0.9,
                inherit_previous=True,
            ),
            session_state=state,
        )

        self.assertFalse(decision.need_clarification)

    def test_low_confidence_between_different_planning_modes_asks_for_intent_confirmation(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="换个便宜点的"),
            intent=Intent(city="上海", city_from_message=True),
            message_route=MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.MODIFY_CONSTRAINT,
                planning_mode=PlanningMode.FULL_REPLAN,
                confidence=0.35,
                inherit_previous=True,
                references_previous_route=True,
                candidate_planning_modes=[PlanningMode.FULL_REPLAN, PlanningMode.PARTIAL_REPLAN],
            ),
            session_state=SessionState(session_id="s1", last_intent=Intent(city="上海"), current_routes=[]),
        )

        self.assertTrue(decision.need_clarification)
        self.assertEqual(decision.clarification_type, "intent_disambiguation")
        self.assertEqual(decision.candidate_intents, ["full_replan", "partial_replan"])
        self.assertIn("重新生成", decision.question)
        self.assertIn("换掉", decision.question)

    def test_missing_optional_start_location_does_not_block_route_generation(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="上海一日游，少排队"),
            intent=Intent(city="上海", city_from_message=True, start_location_name=None, preferences=["少排队"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )

        self.assertFalse(decision.need_clarification)

    def test_city_mentioned_in_message_prevents_default_city_clarification_even_if_flag_missing(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="我想在上海一日游"),
            intent=Intent(city="上海", city_from_message=False, preferences=["一日游"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )

        self.assertFalse(decision.need_clarification)

    def test_structured_new_plan_clarification_only_asks_missing_required_fields(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="今天下午在上海户外漫步，有推荐吗"),
            intent=Intent(
                city="上海",
                city_from_message=True,
                start_time="14:00",
                preferences=["户外", "漫步"],
                interest_tags=["户外", "citywalk"],
            ),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )

        self.assertTrue(decision.need_clarification)
        required_ids = [group.id for group in decision.clarification_groups if group.required]
        optional_ids = [group.id for group in decision.clarification_groups if not group.required]
        self.assertNotIn("city", required_ids)
        self.assertIn("time", required_ids)
        self.assertNotIn("trip_goal", required_ids)
        self.assertIn("companions", optional_ids)
        self.assertIn("pace", optional_ids)
        self.assertIn("crowd", optional_ids)
        self.assertEqual(decision.inferred_context["city"], "上海")

    def test_vague_weekend_outing_does_not_treat_llm_defaults_as_explicit(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="我想周末出去玩玩"),
            intent=Intent(
                city="上海",
                city_from_message=False,
                start_time="14:00",
                duration_hours=6,
                people_count=1,
                budget_per_person=300,
                scenario="weekend_outing",
            ),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.96,
            ),
            session_state=SessionState(session_id="s1"),
        )

        self.assertTrue(decision.need_clarification)
        required_ids = [group.id for group in decision.clarification_groups if group.required]
        optional_ids = [group.id for group in decision.clarification_groups if not group.required]
        self.assertIn("city", required_ids)
        self.assertIn("trip_goal", required_ids)
        self.assertIn("time", required_ids)
        self.assertIn("companions", optional_ids)

    def test_missing_city_and_time_are_required_before_new_plan_preferences(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="帮我安排一个路线"),
            intent=Intent(city="上海", city_from_message=False),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )

        self.assertTrue(decision.need_clarification)
        required_ids = [group.id for group in decision.clarification_groups if group.required]
        self.assertIn("city", required_ids)
        self.assertIn("trip_goal", required_ids)
        self.assertIn("time", required_ids)
        time_group = next(group for group in decision.clarification_groups if group.id == "time")
        self.assertIn("几点出发", time_group.title)
        self.assertTrue(all("start_time" in option.value for option in time_group.options))
        self.assertIn("14:00", [option.value["start_time"] for option in time_group.options])


if __name__ == "__main__":
    unittest.main()
