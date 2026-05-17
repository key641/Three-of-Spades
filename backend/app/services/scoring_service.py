from app.schemas.route import RouteScoreBreakdown, RouteStop


class ScoringService:
    """B-owned module: explainable score rules for route comparison."""

    def score(self, stops: list[RouteStop], objective: str) -> RouteScoreBreakdown:
        total_queue = sum(stop.queue_minutes for stop in stops)
        total_cost = sum(stop.estimated_cost for stop in stops)

        queue_score = max(50, 100 - total_queue)
        budget_score = max(50, 100 - max(0, total_cost - 300) // 5)

        if objective == "low_queue":
            queue_score = min(100, queue_score + 8)
        if objective == "budget":
            budget_score = min(100, budget_score + 8)

        return RouteScoreBreakdown(
            quality=86,
            queue=queue_score,
            budget=budget_score,
            distance=82,
            preference=88,
        )

