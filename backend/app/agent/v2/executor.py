from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from app.agent.v2.models import ToolResult, ToolStatus
from app.schemas.intent import Intent
from app.schemas.route import Route
from app.schemas.user import UserProfile
from app.tools.v2.planning import PlanningToolset


class ExecutionOutcome(BaseModel):
    routes: list[Route] = Field(default_factory=list)
    candidate_pois: list[Any] = Field(default_factory=list)
    observations: list[ToolResult] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    status: str = "infeasible"


class BoundedPlanningExecutor:
    MAX_TOOL_STEPS = 5
    MAX_ROUTE_ATTEMPTS = 3
    SOFT_TIMEOUT_SECONDS = 12

    def __init__(self, toolset: PlanningToolset | None = None) -> None:
        self.toolset = toolset or PlanningToolset()

    async def execute(
        self,
        intent: Intent,
        profile: UserProfile,
        strategy_tags: list | None = None,
        strategy_weights=None,
    ) -> ExecutionOutcome:
        observations: list[ToolResult] = []
        started = time.perf_counter()
        shared = {
            "intent": intent,
            "profile": profile,
            "strategy_tags": strategy_tags or [],
            "strategy_weights": strategy_weights,
        }
        search = await self.toolset.gateway.execute("search_pois", {**shared, "limit": 60})
        observations.append(search)
        if search.status != ToolStatus.SUCCESS:
            return ExecutionOutcome(observations=observations, diagnostics=search.diagnostics)
        pois = search.data
        route_attempts = 0
        min_stops_floor = None
        allow_fallback = False
        last_signature = None

        while len(observations) < self.MAX_TOOL_STEPS and route_attempts < self.MAX_ROUTE_ATTEMPTS:
            signature = (len(pois), min_stops_floor, allow_fallback)
            if signature == last_signature:
                break
            last_signature = signature
            route_attempts += 1
            planned = await self.toolset.gateway.execute(
                "generate_routes",
                {
                    **shared,
                    "pois": pois,
                    "min_stops_floor": min_stops_floor,
                    "allow_min_stops_fallback": allow_fallback,
                },
            )
            observations.append(planned)
            if planned.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL} and planned.data:
                return ExecutionOutcome(
                    routes=planned.data,
                    candidate_pois=pois,
                    observations=observations,
                    diagnostics=planned.diagnostics,
                    status="complete" if planned.status == ToolStatus.SUCCESS else "partial",
                )
            if time.perf_counter() - started >= self.SOFT_TIMEOUT_SECONDS:
                break
            diagnosis = await self.toolset.gateway.execute(
                "diagnose_infeasibility", {"diagnostics": planned.diagnostics}
            )
            observations.append(diagnosis)
            action = diagnosis.suggested_next_actions[0] if diagnosis.suggested_next_actions else "clarify_constraints"
            if action == "expand_recall" and len(observations) < self.MAX_TOOL_STEPS:
                expanded = await self.toolset.gateway.execute(
                    "search_pois", {**shared, "limit": 120, "relax_preferences": True}
                )
                observations.append(expanded)
                if expanded.status == ToolStatus.SUCCESS:
                    pois = expanded.data
                    continue
            if action == "reduce_min_stops":
                min_stops_floor = 2
                allow_fallback = True
                continue
            break

        diagnostics = observations[-1].diagnostics if observations else {}
        return ExecutionOutcome(
            candidate_pois=pois,
            observations=observations,
            diagnostics=diagnostics,
            status="infeasible",
        )
