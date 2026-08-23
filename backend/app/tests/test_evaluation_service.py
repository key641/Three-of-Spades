from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.api import evaluation as evaluation_api
from app.main import app
from app.schemas.chat import AgentTraceStep, ChatResponse
from app.schemas.evaluation import EvaluationCase, EvaluationExpectation, EvaluationRunRequest
from app.schemas.intent import Intent
from app.services.evaluation_service import EvaluationService
from app.services.evaluation_service import DEFAULT_EVALUATION_CASES


class FakeOrchestrator:
    async def handle_message(self, request):
        return ChatResponse(
            session_id=request.session_id,
            message="已生成路线",
            need_clarification=False,
            intent=Intent(city="上海"),
            user_profile=None,
            routes=[],
            agent_trace=[
                AgentTraceStep(step="parse_intent", label="识别城市", status="done"),
                AgentTraceStep(step="generate_routes", label="无可行路线", status="fallback"),
            ],
        )


class FailingOrchestrator:
    async def handle_message(self, request):
        raise RuntimeError("boom")


class SlowOrchestrator:
    async def handle_message(self, request):
        await asyncio.sleep(0.05)
        return ChatResponse(session_id=request.session_id, message="late", routes=[], agent_trace=[])


class V2TraceOrchestrator:
    async def handle_message(self, request):
        return ChatResponse(
            session_id=request.session_id,
            message="需要补充信息",
            need_clarification=True,
            intent=Intent(city="北京"),
            routes=[],
            agent_trace=[
                AgentTraceStep(
                    step="understand_turn", label="understand", status="done",
                    details={"patches": [{"op": "replace", "path": "/city", "value": "北京"}]},
                ),
                AgentTraceStep(step="search_pois", label="search", status="done"),
            ],
        )


class InfeasibleOrchestrator:
    async def handle_message(self, request):
        return ChatResponse(
            session_id=request.session_id,
            message="No feasible route under the current hard constraints.",
            need_clarification=False,
            routes=[],
            agent_trace=[],
            planning_outcome="infeasible",
        )


def test_default_evaluation_suite_has_broad_layered_coverage() -> None:
    assert len(DEFAULT_EVALUATION_CASES) == 20
    categories = {case.category for case in DEFAULT_EVALUATION_CASES}
    assert {"意图理解", "起点定位", "追问决策", "路线生成", "偏好遵循", "多轮状态", "鲁棒性"} <= categories
    assert sum(bool(case.turns) for case in DEFAULT_EVALUATION_CASES) >= 4
    assert sum(case.start_lat is not None for case in DEFAULT_EVALUATION_CASES) >= 4


def test_evaluation_reports_problem_step_and_intermediate_warnings() -> None:
    service = EvaluationService(orchestrator_factory=FakeOrchestrator)
    request = EvaluationRunRequest(
        cases=[
            EvaluationCase(
                name="路线必须生成",
                message="上海一日游",
                expectation=EvaluationExpectation(expected_city="上海", min_routes=1),
            )
        ]
    )

    response = asyncio.run(service.run(request))

    assert response.summary.failed == 1
    assert response.results[0].problem_step == "generate_routes"
    assert response.results[0].warning_steps == ["generate_routes"]
    assert response.results[0].input.message == "上海一日游"
    assert response.results[0].output is not None


def test_evaluation_captures_unhandled_exception_without_stopping_batch() -> None:
    service = EvaluationService(orchestrator_factory=FailingOrchestrator)
    request = EvaluationRunRequest(
        cases=[
            EvaluationCase(name="case 1", message="输入 1"),
            EvaluationCase(name="case 2", message="输入 2"),
        ]
    )

    response = asyncio.run(service.run(request))

    assert response.summary.total == 2
    assert response.summary.failed == 2
    assert all(result.problem_step == "exception" for result in response.results)
    assert all(result.error == "RuntimeError: boom" for result in response.results)


def test_evaluation_api_returns_batch_inputs_outputs_and_steps() -> None:
    original = evaluation_api.evaluation_service
    evaluation_api.evaluation_service = EvaluationService(orchestrator_factory=FakeOrchestrator)
    try:
        response = TestClient(app).post(
            "/api/evaluation/run",
            json={"cases": [{"name": "API case", "message": "上海一日游"}]},
        )
    finally:
        evaluation_api.evaluation_service = original

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["input"]["message"] == "上海一日游"
    assert payload["results"][0]["output"]["agent_trace"][0]["step"] == "parse_intent"


def test_eval_v3_reports_stability_and_versions() -> None:
    service = EvaluationService(orchestrator_factory=FakeOrchestrator)
    response = asyncio.run(service.run(EvaluationRunRequest(
        cases=[EvaluationCase(
            name="stable",
            message="test",
            expectation=EvaluationExpectation(min_routes=0, require_planning_outcome=False),
        )],
        repeat_count=3,
        model_version="test-model",
        prompt_version="understanding-v2",
    )))

    assert response.results[0].attempts == 3
    assert response.results[0].passed_attempts == 3
    assert response.results[0].stable_pass is True
    assert response.summary.stable_pass_rate == 1
    assert response.summary.versions["model"] == "test-model"


def test_eval_v3_times_out_a_stuck_case_without_stopping_batch() -> None:
    service = EvaluationService(orchestrator_factory=SlowOrchestrator)
    request = EvaluationRunRequest(
        cases=[EvaluationCase(name="slow", message="test")],
        case_timeout_seconds=1.0,
    ).model_copy(update={"case_timeout_seconds": 0.01})

    response = asyncio.run(service.run(request))

    assert response.results[0].problem_step == "timeout"
    assert response.results[0].stable_pass is False


def test_eval_v3_checks_golden_patch_state_and_tool_calls() -> None:
    service = EvaluationService(orchestrator_factory=V2TraceOrchestrator)
    response = asyncio.run(service.run(EvaluationRunRequest(cases=[EvaluationCase(
        name="golden",
        message="北京周末游",
        expectation=EvaluationExpectation(
            golden_patch=[{"op": "replace", "path": "/city", "value": "北京"}],
            golden_state={"city": "北京"},
            required_tool_calls=["search_pois"],
            min_routes=0,
        ),
    )])))

    assert response.results[0].passed is True
    assert response.results[0].observed_tool_calls == ["search_pois"]


def test_eval_treats_explicit_infeasible_as_terminal_planning_outcome() -> None:
    service = EvaluationService(orchestrator_factory=InfeasibleOrchestrator)
    response = asyncio.run(service.run(EvaluationRunRequest(cases=[EvaluationCase(
        name="infeasible",
        message="Plan an impossible route",
        expectation=EvaluationExpectation(min_routes=0, expect_trace=False),
    )])))

    assert response.results[0].passed is True
    assert "no_planning_outcome" not in response.results[0].failure_codes
