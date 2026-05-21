from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.agent.orchestrator import AgentOrchestrator  # noqa: E402
from app.schemas.chat import ChatRequest, ChatResponse  # noqa: E402


@dataclass(frozen=True)
class DemoCase:
    name: str
    message: str
    expected_city: str | None = None
    min_routes: int = 0
    expect_trace: bool = True
    session_id: str = "demo_cases"
    user_id: str = "user_demo"
    onboarding_city: str | None = None


@dataclass(frozen=True)
class DemoResult:
    case: DemoCase
    response: ChatResponse
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


DEFAULT_CASES = [
    DemoCase(
        name="上海半天 citywalk",
        message="上海半天 citywalk，2人，人均300，少排队",
        expected_city="上海",
        min_routes=1,
        onboarding_city="北京",
    ),
    DemoCase(
        name="上海多轮预算和排队调整",
        message="预算低一点，别排队",
        expected_city="上海",
        min_routes=1,
    ),
    DemoCase(
        name="上一轮路线交通追问",
        message="就刚刚那条路线，两个地点之间怎么过去",
        min_routes=1,
    ),
    DemoCase(
        name="北京一日游意图识别",
        message="北京一日游，想吃好但别太累",
        expected_city="北京",
        min_routes=0,
    ),
    DemoCase(
        name="显式换城市意图识别",
        message="换成杭州吧",
        expected_city="杭州",
        min_routes=0,
    ),
]


def validate_response(case: DemoCase, response: ChatResponse) -> list[str]:
    failures: list[str] = []
    if case.expected_city:
        actual_city = response.intent.city if response.intent else None
        if actual_city != case.expected_city:
            failures.append(f"expected city {case.expected_city}, got {actual_city}")

    route_count = len(response.routes)
    if route_count < case.min_routes:
        failures.append(f"expected at least {case.min_routes} route(s), got {route_count}")

    if case.expect_trace and not response.agent_trace:
        failures.append("expected non-empty agent_trace")

    if not response.message:
        failures.append("expected non-empty message")

    return failures


async def run_case(orchestrator: AgentOrchestrator, case: DemoCase) -> DemoResult:
    response = await orchestrator.handle_message(
        ChatRequest(
            session_id=case.session_id,
            user_id=case.user_id,
            message=case.message,
            city=case.onboarding_city,
        )
    )
    return DemoResult(case=case, response=response, failures=validate_response(case, response))


async def run_demo_cases(cases: list[DemoCase] | None = None) -> list[DemoResult]:
    orchestrator = AgentOrchestrator()
    results: list[DemoResult] = []
    for case in cases or DEFAULT_CASES:
        results.append(await run_case(orchestrator, case))
    return results


def print_results(results: list[DemoResult], verbose: bool = False) -> None:
    for index, result in enumerate(results, start=1):
        status = "PASS" if result.passed else "FAIL"
        response = result.response
        city = response.intent.city if response.intent else "-"
        route_count = len(response.routes)
        trace_steps = " -> ".join(step.step for step in response.agent_trace) or "-"
        print(f"[{status}] {index}. {result.case.name}")
        print(f"  message: {result.case.message}")
        print(f"  city: {city}; routes: {route_count}; trace: {trace_steps}")
        if verbose:
            print(f"  reply: {response.message}")
        for failure in result.failures:
            print(f"  - {failure}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run A-side demo cases against AgentOrchestrator.")
    parser.add_argument("--verbose", action="store_true", help="print full assistant replies")
    parser.add_argument("--debug-logs", action="store_true", help="show backend error logs while running cases")
    args = parser.parse_args()

    if not args.debug_logs:
        logging.getLogger("app").setLevel(logging.CRITICAL)

    results = asyncio.run(run_demo_cases())
    print_results(results, verbose=args.verbose)
    failed = sum(1 for result in results if not result.passed)
    print(f"\nSummary: {len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
