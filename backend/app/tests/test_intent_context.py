import unittest

from app.agent.intent_context import apply_session_context, is_adjustment_message
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


if __name__ == "__main__":
    unittest.main()
