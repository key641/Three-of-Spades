import unittest

from app.agent.intent_enhancer import enhance_intent_from_message
from app.schemas.intent import Intent


class IntentEnhancerTest(unittest.TestCase):
    def test_extracts_explicit_start_location(self) -> None:
        from_start = enhance_intent_from_message(Intent(city="北京"), "从国贸出发，找个附近餐厅")
        at_start = enhance_intent_from_message(Intent(city="上海"), "我在静安寺，想附近转转")

        self.assertEqual(from_start.start_location_name, "国贸")
        self.assertEqual(at_start.start_location_name, "静安寺")

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
        self.assertIn("美食", intent.interest_tags)
        self.assertIn("少排队", intent.optimization_goals)
        self.assertIn("排队久", intent.avoid_tags)

    def test_extracts_half_day_citywalk_and_start_time(self) -> None:
        intent = enhance_intent_from_message(Intent(), "今晚上海半天 citywalk，想拍照，少走路")

        self.assertEqual(intent.city, "上海")
        self.assertEqual(intent.duration_hours, 4)
        self.assertEqual(intent.start_time, "19:00")
        self.assertIn("citywalk", intent.preferences)
        self.assertIn("拍照", intent.preferences)
        self.assertIn("少走路", intent.optimization_goals)

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

    def test_normalizes_all_preference_and_avoid_aliases(self) -> None:
        base = Intent(
            preferences=["好吃", "高性价比", "打卡", "城市漫步", "带娃"],
            avoid_tags=["人多", "贵", "走路多"],
        )

        intent = enhance_intent_from_message(base, "还想出片、便宜一点，也不想排队")

        self.assertEqual(
            intent.interest_tags,
            ["美食", "拍照", "citywalk", "亲子"],
        )
        self.assertEqual(intent.optimization_goals, ["高性价比", "少排队", "省钱"])
        self.assertEqual(intent.avoid_tags, ["人流密集", "太贵", "步行多", "排队久"])


if __name__ == "__main__":
    unittest.main()
