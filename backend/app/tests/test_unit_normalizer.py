import unittest

from app.agent.schemas import IntentDelta
from app.agent.orchestrator import AgentOrchestrator
from app.agent.unit_normalizer import normalize_delta_units


class UnitNormalizerTest(unittest.TestCase):
    def test_corrects_llm_day_count_to_schema_hours(self) -> None:
        delta = IntentDelta(modified_hard_constraints={"duration_hours": 1, "people_count": 1})

        normalized = normalize_delta_units(delta, "改成上海两个人一天")

        self.assertEqual(normalized.modified_hard_constraints["duration_hours"], 8)
        self.assertEqual(normalized.modified_hard_constraints["people_count"], 2)

    def test_normalizes_related_duration_units(self) -> None:
        cases = [
            ("上海半天 citywalk", 4),
            ("上海玩2天", 16),
            ("上海玩120分钟", 2),
            ("上海玩1小时", 1),
        ]

        for message, expected_hours in cases:
            with self.subTest(message=message):
                delta = IntentDelta(modified_hard_constraints={"duration_hours": 1})

                normalized = normalize_delta_units(delta, message)

                self.assertEqual(normalized.modified_hard_constraints["duration_hours"], expected_hours)

    def test_normalizes_total_budget_to_per_person_budget(self) -> None:
        delta = IntentDelta(modified_hard_constraints={"budget_per_person": 400})

        normalized = normalize_delta_units(delta, "两个人总预算400")

        self.assertEqual(normalized.modified_hard_constraints["people_count"], 2)
        self.assertEqual(normalized.modified_hard_constraints["budget_per_person"], 200)

    def test_keeps_per_person_budget_as_per_person_budget(self) -> None:
        delta = IntentDelta(modified_hard_constraints={"budget_per_person": 400})

        normalized = normalize_delta_units(delta, "两个人人均400以内")

        self.assertEqual(normalized.modified_hard_constraints["people_count"], 2)
        self.assertEqual(normalized.modified_hard_constraints["budget_per_person"], 400)

    def test_normalizes_time_of_day_to_24_hour_clock(self) -> None:
        cases = [
            ("下午两点出发", "14:00"),
            ("晚上7点开始", "19:00"),
            ("09:30出发", "09:30"),
        ]

        for message, expected_time in cases:
            with self.subTest(message=message):
                delta = IntentDelta(modified_hard_constraints={"start_time": "09:00"})

                normalized = normalize_delta_units(delta, message)

                self.assertEqual(normalized.modified_hard_constraints["start_time"], expected_time)

    def test_does_not_treat_soft_degree_or_queue_minutes_as_trip_units(self) -> None:
        delta = IntentDelta()

        low_budget = normalize_delta_units(delta, "预算低一点，别排队")
        queue_event = normalize_delta_units(delta, "餐厅排队 90 分钟，帮我换一个等待时间短的替代方案")

        self.assertNotIn("start_time", low_budget.modified_hard_constraints)
        self.assertNotIn("duration_hours", queue_event.modified_hard_constraints)

    def test_orchestrator_delta_normalization_uses_user_message_units(self) -> None:
        orchestrator = AgentOrchestrator()
        delta = IntentDelta(modified_hard_constraints={"duration_hours": 1, "budget_per_person": 400})

        normalized = orchestrator._normalize_intent_delta(delta, "改成上海两个人一天，总预算400，下午两点出发")

        self.assertEqual(normalized.modified_hard_constraints["duration_hours"], 8)
        self.assertEqual(normalized.modified_hard_constraints["people_count"], 2)
        self.assertEqual(normalized.modified_hard_constraints["budget_per_person"], 200)
        self.assertEqual(normalized.modified_hard_constraints["start_time"], "14:00")


if __name__ == "__main__":
    unittest.main()
