import asyncio

from app.agent.v2.executor import BoundedPlanningExecutor
from app.agent.v2.models import ToolResult, ToolSpec, ToolStatus
from app.schemas.intent import Intent
from app.schemas.route import Route, RouteScoreBreakdown
from app.schemas.user import UserProfile
from app.tools.v2.gateway import AgentTool, ToolGateway


class FailingTool(AgentTool):
    spec = ToolSpec(name="fail", description="test")

    def run(self, payload):
        raise RuntimeError("secret internal failure")


def test_gateway_converts_internal_exception_to_safe_result() -> None:
    gateway = ToolGateway()
    gateway.register(FailingTool())
    result = asyncio.run(gateway.execute("fail", {}))
    assert result.status == ToolStatus.FATAL_ERROR
    assert result.error_code == "RuntimeError"
    assert "secret" not in (result.safe_message or "")


def test_planning_toolset_exposes_required_agent_tools() -> None:
    from app.tools.v2.planning import PlanningToolset

    names = {spec.name for spec in PlanningToolset().gateway.specs()}
    assert names == {
        "resolve_location", "search_pois", "generate_routes", "diagnose_infeasibility",
        "relax_constraints", "replan_route", "answer_route_question",
    }


class FakeGateway:
    def __init__(self) -> None:
        self.calls = []
        self.route_attempts = 0

    async def execute(self, name, payload):
        self.calls.append((name, payload.get("min_stops_floor"), payload.get("limit")))
        if name == "search_pois":
            return ToolResult(call_id="s", tool_name=name, status=ToolStatus.SUCCESS, data=[object()] * 51)
        if name == "diagnose_infeasibility":
            return ToolResult(
                call_id="d", tool_name=name, status=ToolStatus.SUCCESS,
                suggested_next_actions=["reduce_min_stops"],
            )
        self.route_attempts += 1
        if self.route_attempts == 1:
            return ToolResult(
                call_id="r1", tool_name=name, status=ToolStatus.INFEASIBLE,
                diagnostics={"candidate_poi_count": 51},
            )
        return ToolResult(
            call_id="r2", tool_name=name, status=ToolStatus.PARTIAL,
            data=[Route(
                route_id="r1", title="route", objective="balanced", summary="ok",
                total_duration_minutes=60, total_cost_per_person=0, total_queue_minutes=0,
                score=80, score_breakdown=RouteScoreBreakdown(
                    quality=80, queue=80, budget=80, distance=80, preference=80,
                ), stops=[], reasons=["test"],
            )],
        )


class FakeToolset:
    def __init__(self) -> None:
        self.gateway = FakeGateway()


def test_executor_uses_diagnostics_instead_of_expanding_sufficient_recall() -> None:
    executor = BoundedPlanningExecutor(FakeToolset())
    outcome = asyncio.run(executor.execute(Intent(), UserProfile(user_id="u")))
    assert outcome.status == "partial"
    assert len(outcome.routes) == 1
    assert [call[0] for call in executor.toolset.gateway.calls].count("search_pois") == 1
    route_calls = [call for call in executor.toolset.gateway.calls if call[0] == "generate_routes"]
    assert route_calls == [("generate_routes", None, None), ("generate_routes", 2, None)]
