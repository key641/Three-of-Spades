import unittest

from app.agent.intent_enhancer import enhance_intent_from_message
from app.schemas.intent import Intent


class IntentEnhancerTest(unittest.TestCase):
    def test_extracts_city_and_one_day_trip(self) -> None:
        intent = enhance_intent_from_message(Intent(preferences=["一日游"], need_clarification=True), "想要在北京一日游")

        self.assertEqual(intent.city, "北京")
        self.assertEqual(intent.duration_hours, 8)
        self.assertNotIn("一日游", intent.preferences)
        self.assertFalse(intent.need_clarification)

    def test_extracts_people_budget_preferences_and_avoid_tags(self) -> None:
        intent = enhance_intent_from_message(Intent(), "北京一日游，2人，想吃好但别排队，人均200以内")

        self.assertEqual(intent.city, "北京")
        self.assertEqual(intent.people_count, 2)
        self.assertEqual(intent.duration_hours, 8)
        self.assertEqual(intent.budget_per_person, 200)
        self.assertIn("吃好", intent.preferences)
        self.assertIn("少排队", intent.preferences)
        self.assertIn("排队久", intent.avoid_tags)

    def test_extracts_half_day_citywalk_and_start_time(self) -> None:
        intent = enhance_intent_from_message(Intent(), "今晚上海半天 citywalk，想拍照，少走路")

        self.assertEqual(intent.city, "上海")
        self.assertEqual(intent.duration_hours, 4)
        self.assertEqual(intent.start_time, "19:00")
        self.assertIn("citywalk", intent.preferences)
        self.assertIn("拍照", intent.preferences)
        self.assertIn("少走路", intent.preferences)

    def test_keeps_existing_llm_values_when_message_has_no_override(self) -> None:
        base = Intent(city="杭州", duration_hours=3, preferences=["室内"])

        intent = enhance_intent_from_message(base, "不要太累，安静一点")

        self.assertEqual(intent.city, "杭州")
        self.assertEqual(intent.duration_hours, 3)
        self.assertIn("室内", intent.preferences)
        self.assertIn("安静", intent.preferences)

    def test_explicit_message_city_survives_onboarding_merge(self) -> None:
        intent = enhance_intent_from_message(Intent(city="上海"), "我想要在上海一日游")

        self.assertEqual(intent.city, "上海")
        self.assertTrue(intent.city_from_message)


if __name__ == "__main__":
    unittest.main()
