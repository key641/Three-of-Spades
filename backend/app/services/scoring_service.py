from app.schemas.route import RouteScoreBreakdown, RouteStop
from app.schemas.user import StrategyWeights


class ScoringService:
    """B-owned module: explainable score rules for route comparison."""

    def score(
        self,
        stops: list[RouteStop],
        objective: str,
        budget_per_person: int = 300,
        strategy_weights: StrategyWeights | None = None,
    ) -> RouteScoreBreakdown:
        total_queue = sum(stop.queue_minutes for stop in stops)
        total_cost = sum(stop.estimated_cost for stop in stops)
        total_travel = sum(stop.travel_minutes_from_previous or 0 for stop in stops)
        total_distance = sum(stop.distance_km_from_previous or 0 for stop in stops)
        quality_hits = sum(1 for stop in stops if any(tag in stop.tags for tag in ["经典", "文艺", "夜景", "互动体验", "小众"]))
        preference_hits = sum(1 for stop in stops if stop.reason)

        quality_score = self._clamp(78 + quality_hits * 4)
        queue_score = self._clamp(100 - total_queue)
        budget_score = self._clamp(100 - max(0, total_cost - budget_per_person) // 4)
        distance_score = self._clamp(100 - int(total_distance * 5) - total_travel // 2)
        preference_score = self._clamp(72 + preference_hits * 6)

        if objective == "low_queue":
            queue_score = min(100, queue_score + 8)
        if objective == "budget":
            budget_score = min(100, budget_score + 8)
        if objective == "low_walking":
            distance_score = min(100, distance_score + 8)
        if objective in {"food_first", "photo_citywalk", "indoor_rainy"}:
            preference_score = min(100, preference_score + 8)

        return RouteScoreBreakdown(
            quality=quality_score,
            queue=queue_score,
            budget=budget_score,
            distance=distance_score,
            preference=preference_score,
        )

    def overall_score(self, breakdown: RouteScoreBreakdown, weights: StrategyWeights, objective: str) -> int:
        weighted = (
            breakdown.quality * weights.quality
            + breakdown.queue * weights.queue
            + breakdown.distance * weights.distance
            + breakdown.budget * weights.budget
            + breakdown.preference * weights.preference
        )
        objective_bonus = {
            "low_queue": breakdown.queue,
            "budget": breakdown.budget,
            "low_walking": breakdown.distance,
            "food_first": breakdown.preference,
            "photo_citywalk": breakdown.preference,
            "indoor_rainy": breakdown.preference,
        }.get(objective)
        if objective_bonus is not None:
            weighted = weighted * 0.9 + objective_bonus * 0.1
        return self._clamp(round(weighted))

    def _clamp(self, value: int) -> int:
        return max(50, min(100, value))
