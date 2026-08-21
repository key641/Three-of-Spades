import asyncio

from app.agent.v2.runtime import V2AgentRuntime
from app.agent.v2.understanding import TurnUnderstandingService
from app.schemas.chat import ChatRequest
from app.state.repository import InMemoryStateRepository


def runtime_without_llm() -> V2AgentRuntime:
    runtime = V2AgentRuntime(repository=InMemoryStateRepository())
    runtime.understanding = TurnUnderstandingService()
    return runtime


def test_v2_runtime_clarifies_missing_city_after_persisting_patch() -> None:
    runtime = runtime_without_llm()
    response = asyncio.run(runtime.handle_message(ChatRequest(session_id="s1", message="周末想逛逛")))
    assert response.need_clarification
    assert response.planning_outcome == "clarification"
    assert response.state_version == 1
    assert runtime.repository.load("s1") is not None


def test_v2_runtime_plans_and_reuses_idempotent_response() -> None:
    runtime = runtime_without_llm()
    request = ChatRequest(
        request_id="request-1",
        session_id="s2",
        user_id="user_demo",
        message="北京半日游，少走路",
        city="北京",
    )
    first = asyncio.run(runtime.handle_message(request))
    second = asyncio.run(runtime.handle_message(request))
    assert first.routes
    assert first.planning_outcome in {"complete", "partial"}
    assert second.trace_id == first.trace_id
    assert second.state_version == first.state_version


def test_v2_runtime_preserves_explicit_start_on_next_gps_turn() -> None:
    runtime = runtime_without_llm()
    asyncio.run(runtime.handle_message(ChatRequest(
        session_id="s3", message="从国贸出发，北京半日游", city="北京",
        start_lat=39.99, start_lng=116.47,
    )))
    asyncio.run(runtime.handle_message(ChatRequest(
        session_id="s3", message="预算降到人均200，其他不变", city="北京",
        start_lat=39.90, start_lng=116.30,
    )))
    state = runtime.repository.load("s3")
    assert state.start_location.value.name == "国贸"
    assert state.scalar_value("budget_per_person") == 200
