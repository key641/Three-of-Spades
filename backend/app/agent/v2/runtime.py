from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import uuid

from app.agent.orchestrator import AgentOrchestrator
from app.agent.v2.compatibility import legacy_to_v2, restored_routes, state_to_intent
from app.agent.v2.executor import BoundedPlanningExecutor
from app.agent.v2.models import PlanningOutcomeV2, StateEvent, TripStateV2
from app.agent.v2.policy import AgentPolicy, DecisionType
from app.agent.v2.reducer import reduce_state
from app.agent.v2.response_composer import ResponseComposer
from app.agent.v2.understanding import TurnUnderstandingService
from app.agent.v2.verifier import OutcomeVerifier
from app.config import PROJECT_ROOT, settings
from app.schemas.chat import AgentTraceStep, ChatRequest, ChatResponse
from app.schemas.intent import Intent
from app.services.profile_service import ProfileService
from app.state.repository import SQLiteStateRepository, StateConflictError, StateRepository


logger = logging.getLogger("app.agent.v2.runtime")


class V2AgentRuntime:
    def __init__(
        self,
        legacy: AgentOrchestrator | None = None,
        repository: StateRepository | None = None,
    ) -> None:
        self.legacy = legacy or AgentOrchestrator()
        self.repository = repository or SQLiteStateRepository(_database_path(settings.database_url))
        self.understanding = TurnUnderstandingService(self.legacy.llm_client)
        self.policy = AgentPolicy()
        self.executor = BoundedPlanningExecutor()
        self.verifier = OutcomeVerifier()
        self.composer = ResponseComposer()
        self.profile_service = ProfileService()
        self._locks: dict[str, asyncio.Lock] = {}

    async def handle_message(self, request: ChatRequest, progress_callback=None, routes_callback=None) -> ChatResponse:
        lock = self._locks.setdefault(request.session_id, asyncio.Lock())
        async with lock:
            if request.request_id:
                cached = self.repository.get_request_result(request.request_id)
                if cached:
                    return ChatResponse.model_validate(cached)
            response = await self._handle(request, progress_callback, routes_callback)
            if request.request_id:
                self.repository.save_request_result(
                    request.request_id, request.session_id, response.model_dump(mode="json")
                )
            return response

    async def shadow_observe(self, request: ChatRequest, v1_response: ChatResponse | None = None) -> None:
        state = self._load_state(request.session_id)
        understanding = await self.understanding.understand(request, state)
        candidate, _, _ = reduce_state(state, understanding, f"shadow_{uuid.uuid4().hex}")
        decision = self.policy.decide(candidate, understanding)
        shadow_route_count = 0
        shadow_status = decision.decision.value
        if decision.decision in {DecisionType.PLAN, DecisionType.REPLAN}:
            intent = state_to_intent(candidate)
            profile = self.profile_service.get_profile(request.user_id)
            tags = self.profile_service.strategy_service.infer_tags(request.message, intent, profile)
            weights = self.profile_service.build_strategy_weights(intent, profile, tags)
            outcome = await self.executor.execute(intent, profile, tags, weights)
            report = self.verifier.verify(outcome.routes, intent, profile, outcome.candidate_pois)
            shadow_route_count = len(report.valid_routes)
            shadow_status = "complete" if shadow_route_count >= 3 else "partial" if shadow_route_count else outcome.status
        logger.info(
            "v2 shadow comparison session_id=%s turn_type=%s decision=%s patches=%s v1_routes=%s v2_routes=%s v2_status=%s",
            request.session_id,
            understanding.turn_type,
            decision.decision.value,
            len(understanding.state_patch),
            len(v1_response.routes) if v1_response else None,
            shadow_route_count,
            shadow_status,
        )

    async def _handle(self, request: ChatRequest, progress_callback, routes_callback) -> ChatResponse:
        trace_id = f"trace_{uuid.uuid4().hex}"
        turn_id = f"turn_{uuid.uuid4().hex}"
        trace: list[AgentTraceStep] = []

        async def emit(step: AgentTraceStep) -> None:
            trace.append(step)
            if progress_callback:
                result = progress_callback(step)
                if asyncio.iscoroutine(result):
                    await result

        state = self._load_state(request.session_id)
        understanding = await self.understanding.understand(request, state)
        await emit(AgentTraceStep(
            step="understand_turn",
            label=f"统一理解本轮需求：{understanding.turn_type}",
            status="done",
            details={
                "mode": understanding.mode,
                "confidence": understanding.confidence,
                "patches": [patch.model_dump(mode="json") for patch in understanding.state_patch],
            },
        ))
        updated, event, summary = reduce_state(state, understanding, turn_id)
        try:
            self.repository.save(updated, event, expected_version=state.state_version)
        except StateConflictError:
            state = self._load_state(request.session_id)
            updated, event, summary = reduce_state(state, understanding, turn_id)
            self.repository.save(updated, event, expected_version=state.state_version)
        await emit(AgentTraceStep(
            step="reduce_state",
            label="合并权威旅行状态",
            status="done",
            details={"state_version": updated.state_version, **summary.model_dump()},
        ))

        decision = self.policy.decide(updated, understanding)
        await emit(AgentTraceStep(
            step="decide_action",
            label=f"决策：{decision.decision.value}",
            status="done",
            details=decision.model_dump(mode="json"),
        ))
        if decision.decision == DecisionType.CLARIFY:
            response = ChatResponse(
                session_id=request.session_id,
                message=decision.question or "还需要补充一些信息。",
                need_clarification=True,
                clarifying_question=decision.question,
                clarification_type="blocking_fields",
                inferred_context={"blocking_fields": decision.blocking_fields},
                intent=state_to_intent(updated),
                user_profile=None,
                routes=restored_routes(updated),
                agent_trace=trace,
                planning_outcome="clarification",
                state_version=updated.state_version,
                trace_id=trace_id,
            )
            return response

        if decision.decision == DecisionType.ANSWER_FROM_STATE:
            legacy_state = self.legacy.memory.get_state(request.session_id)
            legacy_state.last_intent = state_to_intent(updated)
            legacy_state.current_routes = restored_routes(updated)
            self.legacy.memory.save_state(legacy_state)
            response = await self.legacy.handle_message(request, progress_callback, routes_callback)
            response.state_version = updated.state_version
            response.trace_id = trace_id
            response.planning_outcome = "complete"
            response.agent_trace = [*trace, *response.agent_trace]
            return response

        intent = self._execution_intent(state_to_intent(updated))
        profile = self.profile_service.get_profile(request.user_id)
        strategy_tags = self.profile_service.strategy_service.infer_tags(request.message, intent, profile)
        strategy_weights = self.profile_service.build_strategy_weights(intent, profile, strategy_tags)
        outcome = await self.executor.execute(intent, profile, strategy_tags, strategy_weights)
        for observation in outcome.observations:
            await emit(AgentTraceStep(
                step=observation.tool_name,
                label=f"工具 {observation.tool_name}：{observation.status.value}",
                status="done" if observation.status.value in {"success", "partial"} else "fallback",
                details={
                    "call_id": observation.call_id,
                    "duration_ms": observation.duration_ms,
                    "diagnostics": observation.diagnostics,
                    "suggested_next_actions": observation.suggested_next_actions,
                    "error_code": observation.error_code,
                },
            ))
        report = self.verifier.verify(outcome.routes, intent, profile, outcome.candidate_pois)
        routes = report.valid_routes
        if routes_callback and routes:
            callback_result = routes_callback(routes)
            if asyncio.iscoroutine(callback_result):
                await callback_result
        status = "complete" if len(routes) >= 3 else "partial" if routes else "infeasible"
        degradation_steps = list(outcome.diagnostics.get("degradation_steps") or [])
        warnings = list(dict.fromkeys(issue.message for issue in report.issues if not issue.hard))
        message = (
            self.composer.compose_routes(
                intent, routes, degradation_steps=degradation_steps, warnings=warnings
            )
            if routes
            else self.composer.compose_infeasible(intent, _dominant_diagnostics(outcome))
        )
        updated.current_route_ids = [route.route_id for route in routes]
        updated.route_snapshots = [route.model_dump(mode="json") for route in routes]
        updated.active_route_id = updated.current_route_ids[0] if updated.current_route_ids else None
        updated.last_outcome = PlanningOutcomeV2(
            status=status,
            route_ids=updated.current_route_ids,
            diagnostics=outcome.diagnostics,
        )
        updated.state_version += 1
        outcome_event = StateEvent(
            event_id=f"evt_{uuid.uuid4().hex}", session_id=request.session_id, turn_id=turn_id,
            base_version=updated.state_version - 1, new_version=updated.state_version,
            event_type="planning_outcome", patches=[], created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.repository.save(updated, outcome_event, expected_version=updated.state_version - 1)
        return ChatResponse(
            session_id=request.session_id,
            message=message,
            need_clarification=False,
            intent=intent,
            user_profile=profile,
            routes=routes,
            agent_trace=trace,
            planning_outcome=status,
            state_version=updated.state_version,
            trace_id=trace_id,
            warnings=warnings,
            degradation={"level": max((route.degradation_level for route in routes), default=0), "changes": degradation_steps},
        )

    def _execution_intent(self, intent: Intent) -> Intent:
        """为指定区域的执行阶段校正不在区域附近的默认/GPS 起点。"""
        if not (intent.target_district or intent.target_business_area):
            return intent

        regional_intent = intent.model_copy(update={"start_lat": None, "start_lng": None})
        regional_pois = self.executor.toolset.poi_service.search(
            regional_intent,
            limit=80,
            relax_preferences=True,
        )
        if not regional_pois:
            return intent

        is_far_from_region = (
            intent.start_lat is not None
            and intent.start_lng is not None
            and self.legacy._min_distance_to_pois(intent.start_lat, intent.start_lng, regional_pois) > 8.0
        )
        if intent.start_lat is not None and intent.start_lng is not None and not is_far_from_region:
            return intent

        region_name = intent.target_business_area or intent.target_district or "目标区域"
        return intent.model_copy(
            update={
                "start_location_name": f"{region_name}附近",
                "start_lat": sum(poi.lat for poi in regional_pois) / len(regional_pois),
                "start_lng": sum(poi.lng for poi in regional_pois) / len(regional_pois),
            }
        )

    def _load_state(self, session_id: str) -> TripStateV2:
        state = self.repository.load(session_id)
        if state is not None:
            return state
        legacy_state = self.legacy.memory.get_state(session_id)
        return legacy_to_v2(session_id, legacy_state)


class AgentRuntimeRouter:
    def __init__(self) -> None:
        self.v1 = AgentOrchestrator()
        self.v2 = V2AgentRuntime(self.v1)

    async def handle_message(self, request: ChatRequest, progress_callback=None, routes_callback=None) -> ChatResponse:
        mode = settings.agent_runtime_version.strip().lower()
        if mode == "v2":
            return await self.v2.handle_message(request, progress_callback, routes_callback)
        response = await self.v1.handle_message(request, progress_callback, routes_callback)
        if mode == "shadow":
            asyncio.create_task(self._safe_shadow(request, response))
        return response

    async def _safe_shadow(self, request: ChatRequest, v1_response: ChatResponse) -> None:
        try:
            await self.v2.shadow_observe(request, v1_response)
        except Exception:
            logger.exception("v2 shadow failed session_id=%s", request.session_id)


def _database_path(database_url: str) -> Path:
    raw = database_url.removeprefix("sqlite:///")
    path = Path(raw)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / "backend" / path).resolve()


def _dominant_diagnostics(outcome) -> dict:
    for observation in reversed(outcome.observations):
        if observation.tool_name == "diagnose_infeasibility" and isinstance(observation.data, dict):
            return observation.data
    return outcome.diagnostics
