import unittest

from app.agent.intent_confidence import IntentConfidenceCalibrator
from app.agent.message_router import MessageIntentType, MessageRoute, PlanningMode, TurnType
from app.agent.schemas import SessionState
from app.schemas.intent import Intent


class IntentConfidenceCalibratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calibrator = IntentConfidenceCalibrator()

    def test_missing_llm_confidence_is_calibrated_from_context_not_zero(self) -> None:
        route = MessageRoute(
            intent_type=MessageIntentType.NEW_PLAN,
            turn_type=TurnType.NEW_PLAN,
            planning_mode=PlanningMode.NEW_PLAN,
        )

        calibrated = self.calibrator.calibrate(route, "我想去上海一日游", SessionState(session_id="s1"), source="llm")

        self.assertGreater(calibrated.confidence, 0)
        self.assertEqual(calibrated.confidence_source, "后端校准")
        self.assertTrue(any("模型未返回置信度" in reason for reason in calibrated.confidence_reasons))

    def test_ambiguous_candidate_modes_are_low_confidence_with_reason(self) -> None:
        route = MessageRoute(
            intent_type=MessageIntentType.MODIFY_PLAN,
            turn_type=TurnType.MODIFY_CONSTRAINT,
            planning_mode=PlanningMode.FULL_REPLAN,
            candidate_planning_modes=[PlanningMode.FULL_REPLAN, PlanningMode.PARTIAL_REPLAN],
            confidence=0.9,
        )

        calibrated = self.calibrator.calibrate(
            route,
            "换个便宜点的",
            SessionState(session_id="s1", last_intent=Intent(city="上海")),
            source="llm",
        )

        self.assertLess(calibrated.confidence, 0.5)
        self.assertIn("存在多个候选规划方式", calibrated.confidence_reasons)
        self.assertEqual(calibrated.confidence_source, "后端校准")

    def test_rule_fallback_keeps_rule_source_and_fixed_score(self) -> None:
        route = MessageRoute(
            intent_type=MessageIntentType.REPLAN,
            turn_type=TurnType.MODIFY_CONSTRAINT,
            planning_mode=PlanningMode.PARTIAL_REPLAN,
            confidence=0.55,
        )

        calibrated = self.calibrator.calibrate(
            route,
            "换一家",
            SessionState(session_id="s1", last_intent=Intent(city="上海")),
            source="rule_fallback",
        )

        self.assertEqual(calibrated.confidence, 0.55)
        self.assertEqual(calibrated.confidence_source, "规则兜底")


if __name__ == "__main__":
    unittest.main()
