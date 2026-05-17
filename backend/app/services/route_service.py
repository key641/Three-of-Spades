from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RoutePlanResponse, RouteStop
from app.services.scoring_service import ScoringService


class RouteService:
    """B-owned module: creates route candidates and score breakdowns."""

    def __init__(self) -> None:
        self.scoring_service = ScoringService()

    def generate_routes(self, request: RoutePlanRequest) -> RoutePlanResponse:
        pois = request.candidate_pois
        if not pois:
            return RoutePlanResponse(routes=[])

        objectives = [
            ("balanced", "综合最优路线"),
            ("low_queue", "少排队轻松路线"),
            ("budget", "更省钱路线"),
        ]

        routes = [self._build_route(pois, objective, title) for objective, title in objectives]
        return RoutePlanResponse(routes=routes)

    def _build_route(self, pois: list[POI], objective: str, title: str) -> Route:
        ordered = self._order_pois(pois, objective)
        stops: list[RouteStop] = []
        current_hour = 14
        current_minute = 0

        for poi in ordered[:4]:
            start = f"{current_hour:02d}:{current_minute:02d}"
            total_minutes = current_hour * 60 + current_minute + poi.visit_duration_minutes
            current_hour = total_minutes // 60
            current_minute = total_minutes % 60
            end = f"{current_hour:02d}:{current_minute:02d}"
            stops.append(
                RouteStop(
                    poi_id=poi.id,
                    name=poi.name,
                    category=poi.category,
                    start_time=start,
                    end_time=end,
                    estimated_cost=poi.avg_price,
                    queue_minutes=poi.queue_minutes,
                    tags=poi.tags,
                )
            )

        score_breakdown = self.scoring_service.score(stops, objective)
        return Route(
            route_id=f"route_{objective}",
            title=title,
            objective=objective,
            summary="基于预算、排队、评分和偏好生成的路线方案。",
            total_duration_minutes=sum(p.visit_duration_minutes for p in ordered[:4]),
            total_cost_per_person=sum(p.avg_price for p in ordered[:4]),
            total_queue_minutes=sum(p.queue_minutes for p in ordered[:4]),
            score=round(sum(score_breakdown.model_dump().values()) / 5),
            score_breakdown=score_breakdown,
            stops=stops,
            reasons=["路线节奏清晰", "预算可控", "匹配当前偏好"],
        )

    def _order_pois(self, pois: list[POI], objective: str) -> list[POI]:
        if objective == "low_queue":
            return sorted(pois, key=lambda poi: (poi.queue_minutes, -poi.rating))
        if objective == "budget":
            return sorted(pois, key=lambda poi: (poi.avg_price, -poi.rating))
        return sorted(pois, key=lambda poi: -poi.rating)

