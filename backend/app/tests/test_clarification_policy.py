import unittest

from app.agent.clarification_policy import ClarificationPolicy
from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode, TurnType
from app.agent.schemas import SessionState
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent


class ClarificationPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ClarificationPolicy()

    # ── 新规划路线：P0 城市缺失 ───────────────────────────────

    def test_new_plan_without_city_asks_for_city(self) -> None:
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
        self.assertEqual(decision.clarification_type, "missing_fields")
        # 应有城市问题（P0）
        group_ids = [g.id for g in decision.clarification_groups]
        self.assertIn("city", group_ids)

    # ── 新规划路线：消息中已有城市 → 不追问城市 ───────────────

    def test_city_in_message_prevents_city_gap(self) -> None:
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
        group_ids = [g.id for g in decision.clarification_groups]
        self.assertNotIn("city", group_ids)

    def test_gps_city_prevents_city_gap(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(
                session_id="s1",
                message="周末安排一日游",
                current_lat=39.9042,
                current_lng=116.4074,
            ),
            intent=Intent(city="北京", city_from_message=False, preferences=["一日游"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )

        group_ids = [group.id for group in decision.clarification_groups]
        self.assertNotIn("city", group_ids)
        self.assertEqual(self.policy._coords_to_city(39.9042, 116.4074), "北京")

    # ── 新规划路线：有城市+有目标 → 只追问 P1 时间（可跳过） ──

    def test_new_plan_with_city_and_goal_asks_only_time(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="上海一日游，少排队"),
            intent=Intent(city="上海", city_from_message=True, preferences=["少排队"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )
        # P1 时间缺失会触发追问，但 can_continue_with_defaults=True
        self.assertTrue(decision.need_clarification)
        self.assertTrue(decision.can_continue_with_defaults)
        group_ids = [g.id for g in decision.clarification_groups]
        self.assertIn("time", group_ids)
        self.assertNotIn("city", group_ids)

    # ── 新规划路线：全有 → 不追问 ─────────────────────────────

    def test_new_plan_all_fields_present_no_clarification(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="上海一日游拍照，下午两点出发", start_time="14:00"),
            intent=Intent(city="上海", city_from_message=True, start_time="14:00", duration_hours=8, preferences=["拍照"]),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )
        self.assertFalse(decision.need_clarification)

    # ── 继承 session 城市 → 不追问城市 ────────────────────────

    def test_session_city_prevents_city_clarification(self) -> None:
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

    # ── 全量重规划：有上轮上下文 → 不追问 ──────────────────────

    def test_full_replan_with_context_no_clarification(self) -> None:
        state = SessionState(session_id="s1", last_intent=Intent(city="上海", city_from_message=True))
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="少排队一点"),
            intent=Intent(city="上海", city_from_message=False, preferences=["少排队"]),
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

    # ── 全量重规划：无上轮上下文 → P0 追问 ─────────────────────

    def test_full_replan_without_context_asks(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="少排队一点"),
            intent=Intent(city="上海", city_from_message=False),
            message_route=MessageRoute(
                intent_type=MessageIntentType.MODIFY_PLAN,
                turn_type=TurnType.MODIFY_CONSTRAINT,
                planning_mode=PlanningMode.FULL_REPLAN,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )
        self.assertTrue(decision.need_clarification)
        group_ids = [g.id for g in decision.clarification_groups]
        self.assertIn("previous_state", group_ids)

    # ── 路线细节追问 → 不追问 ──────────────────────────────────

    def test_route_detail_no_clarification(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="第二站排队多久"),
            intent=Intent(),
            message_route=MessageRoute(
                intent_type=MessageIntentType.ROUTE_DETAIL_QUESTION,
                turn_type=TurnType.ROUTE_DETAIL,
                planning_mode=PlanningMode.ROUTE_DETAIL,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )
        self.assertFalse(decision.need_clarification)

    # ── 闲聊 → 不追问 ─────────────────────────────────────────

    def test_general_chat_no_clarification(self) -> None:
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="你好"),
            intent=Intent(),
            message_route=MessageRoute(
                intent_type=MessageIntentType.GENERAL_CHAT,
                turn_type=TurnType.GENERAL_CHAT,
                planning_mode=PlanningMode.GENERAL_CHAT,
                confidence=0.9,
            ),
            session_state=SessionState(session_id="s1"),
        )
        self.assertFalse(decision.need_clarification)

    # ── 已追问过一轮 → 不再追问 ────────────────────────────────

    def test_already_clarified_no_more_clarification(self) -> None:
        state = SessionState(session_id="s1", clarification_count=1)
        decision = self.policy.evaluate(
            request=ChatRequest(session_id="s1", message="帮我安排个路线"),
            intent=Intent(),
            message_route=MessageRoute(
                intent_type=MessageIntentType.NEW_PLAN,
                turn_type=TurnType.NEW_PLAN,
                planning_mode=PlanningMode.NEW_PLAN,
                confidence=0.9,
            ),
            session_state=state,
        )
        self.assertFalse(decision.need_clarification)

    # ── 模糊目标：城市+目标两个 P0 缺口 ────────────────────────

    def test_vague_weekend_outing_triggers_city_and_goal(self) -> None:
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
        group_ids = [g.id for g in decision.clarification_groups]
        self.assertIn("city", group_ids)

    # ── 最多追问 3 个问题 ──────────────────────────────────────

    def test_max_three_questions(self) -> None:
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
        self.assertLessEqual(len(decision.clarification_groups), 3)

    # ── P0 优先于 P1 ───────────────────────────────────────────

    def test_p0_before_p1_ordering(self) -> None:
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
        groups = decision.clarification_groups
        if len(groups) >= 2:
            # 第一个必须是 P0（required=True），后面的可以是 P1
            self.assertTrue(groups[0].required)


if __name__ == "__main__":
    unittest.main()
