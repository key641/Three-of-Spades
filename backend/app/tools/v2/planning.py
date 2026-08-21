from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from app.agent.v2.models import ToolResult, ToolSpec, ToolStatus
from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.fine_rank_service import FineRankService
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.replan_service import ReplanService
from app.agent.route_detail_handler import RouteDetailHandler
from app.tools.v2.gateway import AgentTool, ToolGateway


class SearchPOIsTool(AgentTool):
    spec = ToolSpec(
        name="search_pois",
        description="按旅行约束召回候选 POI",
        timeout_ms=4000,
        side_effect="none",
    )

    def __init__(self, service: POIService) -> None:
        self.service = service

    def run(self, payload: dict[str, Any]) -> ToolResult:
        intent: Intent = payload["intent"]
        profile = payload["profile"]
        pois = self.service.search(
            intent,
            user_profile=profile,
            strategy_tags=payload.get("strategy_tags", []),
            limit=int(payload.get("limit", 60)),
            relax_preferences=bool(payload.get("relax_preferences", False)),
        )
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}",
            tool_name=self.spec.name,
            status=ToolStatus.SUCCESS if pois else ToolStatus.INFEASIBLE,
            data=pois,
            diagnostics={"candidate_poi_count": len(pois), **self.service.last_diagnostics},
            suggested_next_actions=[] if pois else ["clarify_area"],
        )


class GenerateRoutesTool(AgentTool):
    spec = ToolSpec(
        name="generate_routes",
        description="使用确定性路线引擎生成并诊断路线",
        timeout_ms=10000,
        side_effect="none",
    )

    def __init__(self, service: RouteService, fine_rank: FineRankService) -> None:
        self.service = service
        self.fine_rank = fine_rank

    def run(self, payload: dict[str, Any]) -> ToolResult:
        intent: Intent = payload["intent"].model_copy(deep=True)
        profile = payload["profile"]
        pois = payload["pois"]
        strategy_tags = payload.get("strategy_tags", [])
        scores, details = self.fine_rank.score_map(
            pois, intent, profile, strategy_tags=strategy_tags, objective="balanced"
        )
        request = RoutePlanRequest(
            intent=intent,
            user_profile=profile,
            strategy_weights=payload.get("strategy_weights"),
            strategy_tags=strategy_tags,
            candidate_pois=pois,
            poi_relevance_scores=scores,
            poi_fine_rank_details=details,
            debug=True,
        )
        min_stops_floor = payload.get("min_stops_floor")
        response = self.service.generate_routes(
            request,
            min_stops_floor,
            None,
            bool(payload.get("allow_min_stops_fallback", False)),
        )
        route_count = len(response.routes)
        status = ToolStatus.SUCCESS if route_count >= 3 else ToolStatus.PARTIAL if route_count else ToolStatus.INFEASIBLE
        actions = []
        if not route_count:
            actions = ["diagnose_infeasibility"]
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}",
            tool_name=self.spec.name,
            status=status,
            data=response.routes,
            diagnostics={**self.service.last_diagnostics, "route_count": route_count},
            suggested_next_actions=actions,
        )


class DiagnoseInfeasibilityTool(AgentTool):
    spec = ToolSpec(
        name="diagnose_infeasibility",
        description="汇总路线不可行的主导原因并推荐恢复动作",
        timeout_ms=1000,
        side_effect="none",
    )

    def run(self, payload: dict[str, Any]) -> ToolResult:
        diagnostics = payload.get("diagnostics") or {}
        counts: Counter[str] = Counter()
        for objective in (diagnostics.get("objectives") or {}).values():
            counts.update((objective or {}).get("hard_constraint_rejections") or {})
        dominant = counts.most_common(1)[0][0] if counts else "insufficient_combinations"
        candidate_count = int(diagnostics.get("candidate_poi_count") or 0)
        if candidate_count < 20:
            actions = ["expand_recall"]
        elif dominant in {
            "duration_exceeded", "insufficient_combinations", "closed_at_arrival",
            "extreme_budget_exceeded", "budget_exceeded",
        }:
            actions = ["reduce_min_stops"]
        else:
            actions = ["clarify_constraints"]
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}",
            tool_name=self.spec.name,
            status=ToolStatus.SUCCESS,
            data={"dominant_failure": dominant, "rejection_counts": dict(counts)},
            diagnostics={"candidate_poi_count": candidate_count},
            suggested_next_actions=actions,
        )


class ResolveLocationTool(AgentTool):
    spec = ToolSpec(name="resolve_location", description="解析城市内的命名地点", timeout_ms=2000)

    def __init__(self, poi_service: POIService) -> None:
        self.poi_service = poi_service

    def run(self, payload: dict[str, Any]) -> ToolResult:
        city = str(payload.get("city") or "")
        query = str(payload.get("name") or "").strip().lower()
        matches = [
            poi for poi in self.poi_service.all_pois(city)
            if query and query in f"{poi.name} {poi.business_area} {poi.address} {poi.district}".lower()
        ]
        match = max(matches, key=lambda poi: (query in poi.name.lower(), poi.rating, poi.review_count), default=None)
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}", tool_name=self.spec.name,
            status=ToolStatus.SUCCESS if match else ToolStatus.INFEASIBLE,
            data=match,
            diagnostics={"match_count": len(matches)},
            suggested_next_actions=[] if match else ["clarify_location"],
        )


class RelaxConstraintsTool(AgentTool):
    spec = ToolSpec(name="relax_constraints", description="生成受控的临时降级参数", timeout_ms=500)

    def run(self, payload: dict[str, Any]) -> ToolResult:
        level = int(payload.get("level", 0))
        if level <= 0:
            data = {"min_stops_floor": None, "allow_min_stops_fallback": False}
        elif level <= 2:
            data = {"min_stops_floor": 2, "allow_min_stops_fallback": True}
        else:
            data = {"requires_user_confirmation": True}
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}", tool_name=self.spec.name,
            status=ToolStatus.SUCCESS, data=data,
            diagnostics={"level": level},
        )


class ReplanRouteTool(AgentTool):
    spec = ToolSpec(name="replan_route", description="对当前路线执行局部重规划", timeout_ms=10000)

    def __init__(self, service: ReplanService | None = None) -> None:
        self.service = service or ReplanService()

    def run(self, payload: dict[str, Any]) -> ToolResult:
        response = self.service.replan(payload["request"])
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}", tool_name=self.spec.name,
            status=ToolStatus.SUCCESS if response.routes else ToolStatus.INFEASIBLE,
            data=response.routes, diagnostics=response.diagnostics,
        )


class AnswerRouteQuestionTool(AgentTool):
    spec = ToolSpec(name="answer_route_question", description="基于已保存路线回答交通细节", timeout_ms=1000)

    def __init__(self) -> None:
        self.handler = RouteDetailHandler()

    def run(self, payload: dict[str, Any]) -> ToolResult:
        response = self.handler.answer(payload["message"], payload["session_id"], payload["session_state"])
        return ToolResult(
            call_id=f"call_{uuid.uuid4().hex}", tool_name=self.spec.name,
            status=ToolStatus.SUCCESS if not response.need_clarification else ToolStatus.INFEASIBLE,
            data=response,
        )


class PlanningToolset:
    def __init__(
        self,
        poi_service: POIService | None = None,
        route_service: RouteService | None = None,
        fine_rank_service: FineRankService | None = None,
    ) -> None:
        self.poi_service = poi_service or POIService()
        self.route_service = route_service or RouteService()
        self.fine_rank_service = fine_rank_service or FineRankService()
        self.gateway = ToolGateway()
        self.gateway.register(ResolveLocationTool(self.poi_service))
        self.gateway.register(SearchPOIsTool(self.poi_service))
        self.gateway.register(GenerateRoutesTool(self.route_service, self.fine_rank_service))
        self.gateway.register(DiagnoseInfeasibilityTool())
        self.gateway.register(RelaxConstraintsTool())
        self.gateway.register(ReplanRouteTool())
        self.gateway.register(AnswerRouteQuestionTool())
