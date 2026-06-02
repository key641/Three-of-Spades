import unittest

from app.agent.intent_context import apply_session_context, is_adjustment_message
from app.agent.message_router import MessageIntentType, MessageRoute, TurnType
from app.agent.schemas import SessionState
from app.schemas.intent import Intent


class IntentContextTest(unittest.TestCase):
    def test_detects_adjustment_message(self) -> None:
        self.assertTrue(is_adjustment_message("预算低一点，别排队"))
        self.assertTrue(is_adjustment_message("不想排队"))
        self.assertTrue(is_adjustment_message("少走路，不要太累"))
        self.assertTrue(is_adjustment_message("换成杭州吧"))
        self.assertTrue(is_adjustment_message("再安静一点"))
        self.assertFalse(is_adjustment_message("我想在北京一日游"))

    def test_adjustment_inherits_last_intent_and_merges_new_constraints(self) -> None:
        state = SessionState(
            session_id="s1",
            last_intent=Intent(city="上海", duration_hours=8, start_time="09:00", preferences=["拍照"]),
        )
        parsed = Intent(city="上海", duration_hours=6, preferences=["更省钱", "少排队"], avoid_tags=["排队久"])

        intent = apply_session_context(parsed, "预算低一点，别排队", state)

        self.assertEqual(intent.city, "上海")
        self.assertEqual(intent.duration_hours, 8)
        self.assertEqual(intent.start_time, "09:00")
        self.assertEqual(intent.preferences, ["拍照", "更省钱", "少排队"])
        self.assertEqual(intent.avoid_tags, ["排队久"])

    def test_explicit_new_city_starts_new_context(self) -> None:
        state = SessionState(session_id="s1", last_intent=Intent(city="上海", duration_hours=8))
        parsed = Intent(city="北京", city_from_message=True, duration_hours=8)

        intent = apply_session_context(parsed, "我想在北京一日游", state)

        self.assertEqual(intent.city, "北京")
        self.assertEqual(intent.duration_hours, 8)

    def test_adjustment_with_explicit_city_switches_city_and_keeps_constraints(self) -> None:
        state = SessionState(
            session_id="s1",
            last_intent=Intent(city="上海", duration_hours=8, preferences=["少排队"], avoid_tags=["排队久"]),
        )
        parsed = Intent(city="杭州", city_from_message=True, duration_hours=6)

        intent = apply_session_context(parsed, "换成杭州吧", state)

        self.assertEqual(intent.city, "杭州")
        self.assertTrue(intent.city_from_message)
        self.assertEqual(intent.duration_hours, 8)
        self.assertEqual(intent.preferences, ["少排队"])
        self.assertEqual(intent.avoid_tags, ["排队久"])

    def test_followup_adjustment_accumulates_constraints(self) -> None:
        second_turn = Intent(
            city="上海",
            duration_hours=8,
            preferences=["更省钱", "少排队"],
            avoid_tags=["排队久"],
        )
        state = SessionState(session_id="s1", last_intent=second_turn)
        parsed = Intent(preferences=["少走路", "安静"], avoid_tags=["步行多"])

        intent = apply_session_context(parsed, "再少走路一点，安静些", state)

        self.assertEqual(intent.city, "上海")
        self.assertEqual(intent.duration_hours, 8)
        self.assertEqual(intent.preferences, ["更省钱", "少排队", "少走路", "安静"])
        self.assertEqual(intent.avoid_tags, ["排队久", "步行多"])

    def test_add_constraint_preserves_previous_trip_shape_and_scenario(self) -> None:
        state = SessionState(
            session_id="s1",
            last_intent=Intent(
                city="上海",
                people_count=2,
                duration_hours=8,
                start_time="09:00",
                preferences=["拍照"],
                scenario="friends_citywalk",
            ),
        )
        parsed = Intent(city="北京", preferences=["吃好"], scenario="foodie_tour")
        route = MessageRoute(
            intent_type=MessageIntentType.MODIFY_PLAN,
            turn_type=TurnType.ADD_CONSTRAINT,
            inherit_previous=True,
            preserve_scenario=True,
        )

        intent = apply_session_context(parsed, "我还要吃饭", state, route)

        self.assertEqual(intent.city, "上海")
        self.assertEqual(intent.people_count, 2)
        self.assertEqual(intent.duration_hours, 8)
        self.assertEqual(intent.start_time, "09:00")
        self.assertEqual(intent.scenario, "friends_citywalk")
        self.assertEqual(intent.preferences, ["拍照", "吃好"])

    def test_local_route_edit_preserves_hard_constraints_when_llm_infers_new_defaults(self) -> None:
        state = SessionState(
            session_id="s1",
            last_intent=Intent(
                city="上海",
                people_count=1,
                start_time="09:00",
                duration_hours=4,
                budget_per_person=300,
                preferences=["网红打卡"],
                avoid_tags=["商业街"],
                scenario="friends_citywalk",
            ),
        )
        parsed = Intent(
            city="上海",
            people_count=1,
            start_time="12:00",
            duration_hours=2,
            budget_per_person=100,
            preferences=["餐厅", "等待时间短", "替代方案"],
            avoid_tags=["排队久"],
            scenario="restaurant_alternative_short_wait",
        )
        route = MessageRoute(
            intent_type=MessageIntentType.MODIFY_PLAN,
            turn_type=TurnType.MODIFY_CONSTRAINT,
            references_previous_route=True,
            inherit_previous=True,
            preserve_scenario=True,
        )

        intent = apply_session_context(parsed, "餐厅排队 90 分钟，帮我换一个等待时间短的替代方案", state, route)

        self.assertEqual(intent.start_time, "09:00")
        self.assertEqual(intent.duration_hours, 4)
        self.assertEqual(intent.budget_per_person, 300)
        self.assertEqual(intent.scenario, "friends_citywalk")
        self.assertIn("网红打卡", intent.preferences)
        self.assertIn("排队久", intent.avoid_tags)

    def test_local_route_edit_allows_explicit_hard_constraint_changes(self) -> None:
        state = SessionState(
            session_id="s1",
            last_intent=Intent(
                city="上海",
                people_count=1,
                start_time="09:00",
                duration_hours=4,
                budget_per_person=300,
                preferences=["网红打卡"],
                scenario="friends_citywalk",
            ),
        )
        parsed = Intent(
            city="上海",
            people_count=2,
            start_time="12:00",
            duration_hours=2,
            budget_per_person=100,
            preferences=["等待时间短"],
            scenario="restaurant_alternative_short_wait",
        )
        route = MessageRoute(
            intent_type=MessageIntentType.MODIFY_PLAN,
            turn_type=TurnType.MODIFY_CONSTRAINT,
            references_previous_route=True,
            inherit_previous=True,
            preserve_scenario=True,
        )

        intent = apply_session_context(parsed, "换一家，改成两个人下午两点，总预算200", state, route)

        self.assertEqual(intent.people_count, 2)
        self.assertEqual(intent.start_time, "14:00")
        self.assertEqual(intent.budget_per_person, 100)
        self.assertEqual(intent.duration_hours, 4)
        self.assertEqual(intent.scenario, "friends_citywalk")


if __name__ == "__main__":
    unittest.main()
