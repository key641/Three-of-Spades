import unittest

from app.agent.intent_enhancer import enhance_intent_from_message
from app.agent.orchestrator import AgentOrchestrator


class OrchestratorIntentFlowTest(unittest.TestCase):
    def test_fallback_intent_is_enhanced_by_message(self) -> None:
        orchestrator = AgentOrchestrator()
        fallback_intent = orchestrator._mock_parse_intent("想要在北京一日游")

        intent = enhance_intent_from_message(fallback_intent, "想要在北京一日游")

        self.assertEqual(intent.city, "北京")
        self.assertEqual(intent.duration_hours, 8)


if __name__ == "__main__":
    unittest.main()
