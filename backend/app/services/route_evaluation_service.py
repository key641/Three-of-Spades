import json
import logging

from app.llm.base import LLMClient
from app.llm.provider import get_llm_client
from app.schemas.route import Route, RouteEvaluation, RouteEvaluationRequest, RouteEvaluationResponse


logger = logging.getLogger("app.services.route_evaluation")


class RouteEvaluationService:
    """Evaluates generated routes with an LLM-ready interface and deterministic fallback."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_llm_client()

    async def evaluate(self, request: RouteEvaluationRequest) -> RouteEvaluationResponse:
        if not request.routes:
            return RouteEvaluationResponse(evaluations=[])

        try:
            evaluations = await self._evaluate_with_llm(request)
            if evaluations:
                return RouteEvaluationResponse(evaluations=evaluations)
        except Exception as exc:
            logger.exception("route evaluation llm failed fallback=true error=%s", type(exc).__name__)

        return RouteEvaluationResponse(evaluations=[self._fallback_evaluation(route) for route in request.routes])

    async def _evaluate_with_llm(self, request: RouteEvaluationRequest) -> list[RouteEvaluation]:
        payload = {
            "intent": request.intent.model_dump(),
            "user_profile": request.user_profile.model_dump() if request.user_profile else None,
            "routes": [self._route_payload(route) for route in request.routes],
            "output_schema": {
                "evaluations": [
                    {
                        "route_id": "string, must match input route_id",
                        "score": "integer 0-100",
                        "summary": "short Chinese sentence",
                        "highlights": "array of 1-3 short Chinese strings",
                        "risks": "array of 0-3 short Chinese strings",
                        "recommendation": "short Chinese recommendation",
                    }
                ]
            },
        }
        response = await self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "你是路线规划结果评审器。"
                        "只基于输入路线评分，不要编造未提供的地点、时间或价格。"
                        "按用户 intent 和路线 objective，给每条路线 0-100 分、简短总结、亮点、风险和推荐语。"
                        "必须返回 JSON object，顶层字段为 evaluations。"
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            json_mode=True,
        )
        content = response["choices"][0]["message"]["content"]
        loaded = json.loads(content)
        raw_evaluations = loaded.get("evaluations", [])
        route_ids = {route.route_id for route in request.routes}
        evaluations: list[RouteEvaluation] = []
        for raw in raw_evaluations:
            if not isinstance(raw, dict) or raw.get("route_id") not in route_ids:
                continue
            data = dict(raw)
            data["score"] = self._clamp_score(data.get("score"))
            data["source"] = "llm"
            evaluations.append(RouteEvaluation.model_validate(data))
        return evaluations

    def _route_payload(self, route: Route) -> dict:
        return {
            "route_id": route.route_id,
            "title": route.title,
            "objective": route.objective,
            "algorithm_summary": route.summary,
            "algorithm_score": route.score,
            "score_breakdown": route.score_breakdown.model_dump(),
            "total_duration_minutes": route.total_duration_minutes,
            "total_cost_per_person": route.total_cost_per_person,
            "total_queue_minutes": route.total_queue_minutes,
            "total_travel_minutes": route.total_travel_minutes,
            "total_distance_km": route.total_distance_km,
            "reasons": route.reasons,
            "stops": [
                {
                    "name": stop.name,
                    "category": stop.category,
                    "start_time": stop.start_time,
                    "end_time": stop.end_time,
                    "estimated_cost": stop.estimated_cost,
                    "queue_minutes": stop.queue_minutes,
                    "walking_intensity": stop.walking_intensity,
                    "tags": stop.tags,
                    "reason": stop.reason,
                }
                for stop in route.stops
            ],
        }

    def _fallback_evaluation(self, route: Route) -> RouteEvaluation:
        risks: list[str] = []
        if route.total_queue_minutes >= 45:
            risks.append("排队时间偏长")
        if route.total_cost_per_person >= 350:
            risks.append("预算压力较高")
        if route.total_distance_km >= 8:
            risks.append("路程跨度较大")

        highlights = route.reasons[:2] or [route.summary]
        recommendation = "适合作为默认推荐" if route.objective == "balanced" else f"适合偏好“{route.title}”的用户"
        return RouteEvaluation(
            route_id=route.route_id,
            score=route.score,
            summary=route.summary,
            highlights=highlights,
            risks=risks,
            recommendation=recommendation,
            source="fallback",
        )

    def _clamp_score(self, value: object) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, min(score, 100))
