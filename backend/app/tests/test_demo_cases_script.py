import importlib.util
from pathlib import Path
import sys
import unittest

from app.schemas.chat import AgentTraceStep, ChatResponse
from app.schemas.intent import Intent
from app.schemas.route import Route, RouteScoreBreakdown


def load_demo_cases_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "demo_cases.py"
    spec = importlib.util.spec_from_file_location("demo_cases", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DemoCasesScriptTest(unittest.TestCase):
    def build_route(self) -> Route:
        return Route(
            route_id="r1",
            title="测试路线",
            objective="balanced",
            summary="测试",
            total_duration_minutes=60,
            total_cost_per_person=0,
            total_queue_minutes=0,
            score=80,
            score_breakdown=RouteScoreBreakdown(quality=80, queue=80, budget=80, distance=80, preference=80),
            stops=[],
            reasons=["测试"],
        )

    def test_validate_response_accepts_expected_city_routes_and_trace(self) -> None:
        demo_cases = load_demo_cases_module()
        case = demo_cases.DemoCase(name="上海一日游", message="上海一日游", expected_city="上海", min_routes=1)
        response = ChatResponse(
            session_id="s1",
            message="ok",
            need_clarification=False,
            intent=Intent(city="上海"),
            user_profile=None,
            routes=[self.build_route()],
            agent_trace=[AgentTraceStep(step="parse_intent", label="解析意图", status="done")],
        )

        failures = demo_cases.validate_response(case, response)

        self.assertEqual(failures, [])

    def test_validate_response_reports_missing_expectations(self) -> None:
        demo_cases = load_demo_cases_module()
        case = demo_cases.DemoCase(name="上海一日游", message="上海一日游", expected_city="上海", min_routes=1)
        response = ChatResponse(
            session_id="s1",
            message="ok",
            need_clarification=False,
            intent=Intent(city="北京"),
            user_profile=None,
            routes=[],
            agent_trace=[],
        )

        failures = demo_cases.validate_response(case, response)

        self.assertIn("expected city 上海, got 北京", failures)
        self.assertIn("expected at least 1 route(s), got 0", failures)
        self.assertIn("expected non-empty agent_trace", failures)


if __name__ == "__main__":
    unittest.main()
