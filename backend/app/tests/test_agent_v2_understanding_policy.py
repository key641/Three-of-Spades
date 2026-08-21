import asyncio

from app.agent.v2.models import ConstraintSource, TripStateV2
from app.agent.v2.policy import AgentPolicy, DecisionType
from app.agent.v2.reducer import reduce_state
from app.agent.v2.compatibility import state_to_intent
from app.agent.v2.understanding import SYSTEM_PROMPT, TurnUnderstandingService
from app.schemas.chat import ChatRequest


def test_fallback_understanding_prefers_named_start_over_gps() -> None:
    async def run() -> None:
        service = TurnUnderstandingService()
        state = TripStateV2(session_id="s1")
        result = await service.understand(
            ChatRequest(
                session_id="s1",
                message="从国贸出发，北京半日游",
                city="北京",
                start_lat=39.99,
                start_lng=116.47,
            ),
            state,
        )
        starts = [patch for patch in result.state_patch if patch.path == "/start_location"]
        assert len(starts) == 1
        assert starts[0].source == ConstraintSource.USER_EXPLICIT
        assert starts[0].value["name"] == "国贸"

    asyncio.run(run())


def test_policy_only_clarifies_blocking_city() -> None:
    state = TripStateV2(session_id="s1")
    decision = AgentPolicy().decide(state, asyncio.run(TurnUnderstandingService().understand(ChatRequest(message="周末逛逛"), state)))
    assert decision.decision == DecisionType.CLARIFY
    assert decision.blocking_fields == ["city"]


def test_policy_plans_after_city_is_reduced() -> None:
    async def run() -> None:
        state = TripStateV2(session_id="s1")
        understanding = await TurnUnderstandingService().understand(ChatRequest(message="北京周末逛逛"), state)
        state, _, _ = reduce_state(state, understanding, "t1")
        assert AgentPolicy().decide(state, understanding).decision == DecisionType.PLAN

    asyncio.run(run())


def test_time_window_covering_lunch_adds_inferred_meal_role() -> None:
    async def run() -> None:
        state = TripStateV2(session_id="meal-lunch")
        understanding = await TurnUnderstandingService().understand(
            ChatRequest(message="北京从10点开始玩4小时"), state
        )
        meal_patches = [
            patch for patch in understanding.state_patch
            if patch.path.strip("/") == "implicit_needs" and patch.op == "add"
        ]
        assert len(meal_patches) == 1
        assert meal_patches[0].value == ["meal"]
        assert meal_patches[0].source == ConstraintSource.INFERRED
        reduced, _, _ = reduce_state(state, understanding, "meal-turn")
        assert "meal" in state_to_intent(reduced).must_include_roles

    asyncio.run(run())


def test_time_window_outside_meals_does_not_add_meal() -> None:
    state = TripStateV2(session_id="meal-none")
    understanding = asyncio.run(TurnUnderstandingService().understand(
        ChatRequest(message="北京下午两点开始玩3小时"), state
    ))
    assert not any(
        patch.path.strip("/") == "implicit_needs" and patch.op == "add"
        for patch in understanding.state_patch
    )


def test_explicit_no_meal_removes_previously_inferred_meal() -> None:
    async def run() -> None:
        service = TurnUnderstandingService()
        state = TripStateV2(session_id="meal-remove")
        first = await service.understand(ChatRequest(message="北京下午两点玩六小时"), state)
        state, _, _ = reduce_state(state, first, "meal-1")
        second = await service.understand(ChatRequest(message="已经吃过了，不用安排吃饭"), state)
        assert any(
            patch.path.strip("/") == "implicit_needs" and patch.op == "remove"
            for patch in second.state_patch
        )
        state, _, _ = reduce_state(state, second, "meal-2")
        assert "meal" not in state_to_intent(state).must_include_roles

    asyncio.run(run())


def test_understanding_prompt_defines_meal_time_inference() -> None:
    assert "11:30-13:30" in SYSTEM_PROMPT
    assert "17:30-20:00" in SYSTEM_PROMPT
    assert "implicit_needs" in SYSTEM_PROMPT
