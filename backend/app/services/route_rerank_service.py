from dataclasses import dataclass, field

from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RouteStop


@dataclass(frozen=True)
class RouteRerankResult:
    route: Route
    score: int
    reasons: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)


class RouteRerankService:
    """Route-level reranker with dynamic user/objective weights."""

    BASE_WEIGHTS = {
        "poi_model": 0.30,
        "structure": 0.20,
        "travel": 0.15,
        "objective": 0.20,
        "risk": 0.10,
        "diversity": 0.05,
    }
    MAX_OVERLAP = 0.7

    def rerank(
        self,
        routes: list[Route],
        request: RoutePlanRequest,
        poi_by_id: dict[str, POI],
        max_routes: int,
        max_per_objective: int = 1,
    ) -> list[RouteRerankResult]:
        if not routes or max_routes <= 0:
            return []

        selected: list[RouteRerankResult] = []
        remaining = list(routes)
        while remaining and len(selected) < max_routes:
            scored = [
                self.score(route, request, poi_by_id, [item.route for item in selected])
                for route in remaining
            ]
            scored.sort(key=lambda item: item.score, reverse=True)
            chosen = self._choose_next(scored, selected, max_per_objective)
            selected.append(chosen)
            remaining = [route for route in remaining if route is not chosen.route]
        return selected

    def score(
        self,
        route: Route,
        request: RoutePlanRequest,
        poi_by_id: dict[str, POI],
        selected_routes: list[Route] | None = None,
    ) -> RouteRerankResult:
        selected_routes = selected_routes or []
        features = {
            "poi_model": self._poi_model_score(route, request),
            "structure": self._route_structure_score(route, request),
            "travel": self._travel_efficiency_score(route, request),
            "objective": self._objective_match_score(route, request),
            "risk": self._budget_queue_risk_score(route, request, poi_by_id),
            "diversity": self._diversity_score(route, selected_routes, request),
        }
        weights = self._dynamic_weights(route.objective, request)
        score = sum(features[key] * weights[key] for key in weights)
        score += self._coverage_bonus(route, request, selected_routes)
        score -= self._bad_meal_sequence_penalty(route, request)
        score -= self._common_sense_penalty(route, request)
        return RouteRerankResult(
            route=route,
            score=round(max(0, min(1, score)) * 100),
            reasons=self._rerank_reasons(route, features, request),
            features=features,
        )

    def _choose_next(self, scored: list[RouteRerankResult], selected: list[RouteRerankResult], max_per_objective: int) -> RouteRerankResult:
        if not selected:
            return scored[0]
        objective_counts: dict[str, int] = {}
        for item in selected:
            objective_counts[item.route.objective] = objective_counts.get(item.route.objective, 0) + 1
        for item in scored:
            if objective_counts.get(item.route.objective, 0) >= max_per_objective:
                continue
            if all(self._route_overlap(item.route, existing.route) <= self.MAX_OVERLAP for existing in selected):
                return item
        for item in scored:
            if objective_counts.get(item.route.objective, 0) < max_per_objective:
                return item
        return scored[0]

    def _dynamic_weights(self, objective: str, request: RoutePlanRequest) -> dict[str, float]:
        weights = dict(self.BASE_WEIGHTS)
        terms = self._terms(request)
        profile = request.user_profile

        if self._has_any(terms, ["更省钱", "省钱", "低预算", "便宜"]) or profile.budget_sensitivity >= 0.7:
            weights["risk"] += 0.10
            weights["poi_model"] -= 0.05
        if self._has_any(terms, ["少走路", "轻松", "老人", "亲子"]) or profile.walking_tolerance <= 0.35:
            weights["travel"] += 0.12
            weights["structure"] += 0.04
        if self._has_any(terms, ["拍照", "citywalk", "体验感", "出片"]):
            weights["objective"] += 0.08
            weights["structure"] += 0.06
        if self._has_any(terms, ["吃好", "美食", "咖啡探店", "扫街"]):
            weights["objective"] += 0.08
            weights["risk"] += 0.03
        if self._has_any(terms, ["少排队", "人少"]) or profile.crowd_tolerance <= 0.4:
            weights["risk"] += 0.10
        if profile.novelty_preference >= 0.7:
            weights["diversity"] += 0.08
            weights["objective"] += 0.03
        if profile.comfort_preference >= 0.7:
            weights["structure"] += 0.06
            weights["risk"] += 0.05

        objective_bias = {
            "budget": {"risk": 0.16, "poi_model": -0.08},
            "low_walking": {"travel": 0.16, "structure": 0.04},
            "photo_citywalk": {"objective": 0.12, "structure": 0.08},
            "photo_food": {"objective": 0.12, "structure": 0.08},
            "food_first": {"objective": 0.14, "risk": 0.04},
            "indoor_rainy": {"objective": 0.10, "structure": 0.08, "travel": 0.04},
            "night_friendly": {"objective": 0.12, "risk": 0.05},
            "nature_relax": {"objective": 0.10, "travel": 0.08},
        }
        for key, delta in objective_bias.get(objective, {}).items():
            weights[key] += delta

        # Strong intent should not overpay for novelty.
        if len(terms) >= 3 and any(route_term in terms for route_term in ["吃好", "少走路", "更省钱", "拍照"]):
            weights["diversity"] *= 0.7

        return self._normalize_weights(weights)

    def _poi_model_score(self, route: Route, request: RoutePlanRequest) -> float:
        if not route.stops:
            return 0
        scores = [request.poi_relevance_scores.get(stop.poi_id) for stop in route.stops if stop.poi_id in request.poi_relevance_scores]
        if scores:
            return max(0, min(1, (sum(scores) / len(scores) + 0.3) / 1.2))
        return route.score / 100

    def _route_structure_score(self, route: Route, request: RoutePlanRequest) -> float:
        if not route.stops:
            return 0
        roles = self._role_counts(route.stops)
        score = 0.0
        if roles.get("main_activity", 0) >= 1:
            score += 0.35
        if roles.get("meal", 0) >= 1 or roles.get("snack", 0) >= 1:
            score += 0.18
        if roles.get("rest_stop", 0) >= 1 or roles.get("coffee_break", 0) >= 1:
            score += 0.16
        if roles.get("photo_stop", 0) >= 1:
            score += 0.16
        if roles.get("transit_anchor", 0) >= 1:
            score += 0.08
        if self._has_bad_meal_sequence(route, request):
            score -= 0.28
        return self._clip(score + 0.07)

    def _travel_efficiency_score(self, route: Route, request: RoutePlanRequest) -> float:
        if not route.stops:
            return 0
        duration_limit = max(request.intent.duration_hours * 60, 60)
        travel_ratio = route.total_travel_minutes / duration_limit
        distance_ratio = route.total_distance_km / max(len(route.stops) * 4, 1)
        score = 1 - min(0.65, travel_ratio) - min(0.3, distance_ratio * 0.25)
        long_walks = sum(1 for stop in route.stops if stop.transport_mode_from_previous == "walk" and (stop.distance_km_from_previous or 0) > 1)
        walking_sensitivity = 1 - request.user_profile.walking_tolerance
        score -= long_walks * (0.12 + walking_sensitivity * 0.12)
        if any("transit_anchor" in stop.route_roles for stop in route.stops):
            score += 0.06
        return self._clip(score)

    def _objective_match_score(self, route: Route, request: RoutePlanRequest) -> float:
        preference = route.score_breakdown.preference / 100
        roles = self._role_counts(route.stops)
        objective = route.objective
        match = {
            "balanced": self._route_structure_score(route, request),
            "budget": route.score_breakdown.budget / 100,
            "low_walking": route.score_breakdown.distance / 100,
            "food_first": 1.0 if roles.get("meal", 0) or any(self._is_food_stop(stop) for stop in route.stops) else 0.2,
            "photo_food": 1.0 if roles.get("photo_stop", 0) and any(self._is_food_stop(stop) for stop in route.stops) else 0.35,
            "nature_relax": 1.0 if any(stop.primary_category == "nature" or stop.category == "park" for stop in route.stops) else 0.25,
            "photo_citywalk": 1.0 if roles.get("photo_stop", 0) and roles.get("main_activity", 0) else 0.35,
            "indoor_rainy": 1.0 if any(stop.indoor and "main_activity" in stop.route_roles for stop in route.stops) else 0.3,
            "night_friendly": 1.0 if any("night_end" in stop.route_roles or stop.category == "night_view" for stop in route.stops) else 0.35,
        }.get(objective, preference)
        return self._clip(match * 0.7 + preference * 0.3)

    def _budget_queue_risk_score(self, route: Route, request: RoutePlanRequest, poi_by_id: dict[str, POI]) -> float:
        if not route.stops:
            return 0
        profile = request.user_profile
        budget_limit = max(request.intent.budget_per_person, 1)
        budget_over = max(0, route.total_cost_per_person - budget_limit) / budget_limit
        queue_minutes = route.total_queue_minutes
        queue_penalty = min(0.35, queue_minutes / 180 * (1 + (1 - profile.crowd_tolerance)))
        budget_penalty = min(0.35, budget_over * (0.5 + profile.budget_sensitivity))
        closed_penalty = 0.0
        avoid_penalty = 0.0
        avoid_terms = self._terms_from_values([*request.intent.avoid_tags, *profile.avoid_tags])
        for stop in route.stops:
            poi = poi_by_id.get(stop.poi_id)
            if poi and not self._is_open_for_stop(stop, poi):
                closed_penalty += 0.25
            if poi and any(term in self._poi_risk_text(poi) for term in avoid_terms):
                avoid_penalty += 0.18
        return self._clip(1 - budget_penalty - queue_penalty - closed_penalty - avoid_penalty)

    def _diversity_score(self, route: Route, selected_routes: list[Route], request: RoutePlanRequest) -> float:
        if not selected_routes:
            return 0.75
        max_overlap = max(self._route_overlap(route, selected) for selected in selected_routes)
        score = 1 - max_overlap
        if request.user_profile.novelty_preference >= 0.7:
            score = min(1, score + 0.15)
        return self._clip(score)

    def _coverage_bonus(self, route: Route, request: RoutePlanRequest, selected_routes: list[Route]) -> float:
        selected_objectives = {item.objective for item in selected_routes}
        terms = self._terms(request)
        if route.objective in selected_objectives:
            return 0
        if route.objective == "balanced":
            if not selected_routes:
                return 0.03
            return 0.12 if not self._is_strong_single_goal(terms) else 0.05
        if self._has_any(terms, ["更省钱", "省钱", "低预算", "便宜"]) and route.objective == "budget":
            return 0.13
        if self._has_any(terms, ["少走路", "轻松", "老人", "亲子"]) and route.objective == "low_walking":
            return 0.13
        if self._has_any(terms, ["拍照", "citywalk", "体验感", "出片"]) and route.objective in {"photo_citywalk", "photo_food", "nature_relax", "indoor_rainy", "night_friendly"}:
            return 0.12
        if self._has_any(terms, ["吃好", "美食", "咖啡探店", "扫街"]) and route.objective in {"food_first", "photo_food"}:
            return 0.13
        if self._has_any(terms, ["自然", "自然风景", "公园", "风景"]) and route.objective == "nature_relax":
            return 0.13
        return 0.0

    def _is_strong_single_goal(self, terms: set[str]) -> bool:
        goal_groups = [
            ["更省钱", "省钱", "低预算", "便宜"],
            ["少走路", "轻松", "老人", "亲子"],
            ["拍照", "citywalk", "体验感", "出片"],
            ["吃好", "美食", "咖啡探店", "扫街"],
            ["自然", "自然风景", "公园", "风景"],
        ]
        hits = sum(1 for group in goal_groups if self._has_any(terms, group))
        return hits == 1 and len(terms) <= 2

    def _bad_meal_sequence_penalty(self, route: Route, request: RoutePlanRequest) -> float:
        return 0.12 if self._has_bad_meal_sequence(route, request) else 0.0

    def _common_sense_penalty(self, route: Route, request: RoutePlanRequest) -> float:
        terms = self._terms(request)
        explicit_coffee = self._has_any(terms, ["咖啡", "下午茶", "咖啡馆", "咖啡探店", "咖啡路线"])
        rainy = self._has_any(terms, ["雨天", "下雨", "室内", "rain", "indoor_rainy"])
        hot = self._has_any(terms, ["高温", "很热", "炎热", "hot", "避暑"])
        low_energy = self._has_any(terms, ["亲子", "老人", "轻松", "少走路"]) or request.user_profile.walking_tolerance <= 0.35
        penalty = 0.0
        for stop in route.stops:
            minutes = self._parse_time(stop.start_time)
            if self._meal_group(stop) == "coffee" and self._is_late_night(minutes) and not explicit_coffee:
                penalty += 0.22 if route.objective == "night_friendly" else 0.16
            if rainy and not stop.indoor and stop.walking_intensity == "high":
                penalty += 0.10
            if hot and not stop.indoor and stop.walking_intensity == "high":
                penalty += 0.08
            if low_energy and stop.walking_intensity == "high":
                penalty += 0.08
        return min(0.35, penalty)

    def _has_bad_meal_sequence(self, route: Route, request: RoutePlanRequest) -> bool:
        if self._allows_food_crawl(request):
            return False
        groups = [self._meal_group(stop) for stop in route.stops]
        food_groups = [group for group in groups if group in {"meal", "coffee"}]
        if len(food_groups) < 2:
            return False
        return len(food_groups) >= 3 or ("meal" in food_groups and "coffee" in food_groups)

    def _rerank_reasons(self, route: Route, features: dict[str, float], request: RoutePlanRequest) -> list[str]:
        reasons: list[str] = []
        terms = self._terms(request)
        if self._has_any(terms, ["少走路", "轻松"]) and features["travel"] >= 0.7:
            reasons.append("更符合少走路偏好，交通段更短")
        if self._has_any(terms, ["更省钱", "省钱", "少排队"]) and features["risk"] >= 0.7:
            reasons.append("预算和排队风险更稳")
        if self._has_any(terms, ["拍照", "citywalk"]) and features["objective"] >= 0.7:
            reasons.append("保留拍照点和主活动，体验更完整")
        if features["diversity"] >= 0.75:
            reasons.append("和其他路线重复点少，提供另一种体验")
        if features["structure"] >= 0.75:
            reasons.append("路线结构更完整")
        if self._has_context_safe_reason(route, request):
            reasons.append("时间、天气和体力安排更符合实际")
        return reasons[:2]

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        normalized = {key: max(0.01, value) for key, value in weights.items()}
        total = sum(normalized.values())
        return {key: value / total for key, value in normalized.items()}

    def _role_counts(self, stops: list[RouteStop]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for stop in stops:
            for role in stop.route_roles:
                counts[role] = counts.get(role, 0) + 1
        return counts

    def _route_overlap(self, route_a: Route, route_b: Route) -> float:
        ids_a = {stop.poi_id for stop in route_a.stops}
        ids_b = {stop.poi_id for stop in route_b.stops}
        if not ids_a or not ids_b:
            return 0
        return len(ids_a & ids_b) / min(len(ids_a), len(ids_b))

    def _meal_group(self, stop: RouteStop) -> str:
        if "coffee_break" in stop.route_roles or stop.category == "cafe" or stop.meal_type == "cafe":
            return "coffee"
        if "meal" in stop.route_roles or stop.category == "restaurant" or stop.meal_type in {"local_food", "fine_dining"}:
            return "meal"
        if "snack" in stop.route_roles or stop.category == "market" or stop.meal_type in {"light_meal", "fast_food"}:
            return "snack"
        return "none"

    def _is_food_stop(self, stop: RouteStop) -> bool:
        return self._meal_group(stop) in {"meal", "coffee", "snack"}

    def _allows_food_crawl(self, request: RoutePlanRequest) -> bool:
        return self._has_any(self._terms(request), ["美食路线", "扫街", "吃很多家", "小吃街", "多家餐厅", "咖啡探店", "咖啡路线", "多家咖啡"])

    def _is_open_for_stop(self, stop: RouteStop, poi: POI) -> bool:
        start = self._parse_time(stop.start_time)
        open_minutes = self._parse_time(poi.open_time)
        last_entry = self._parse_time(poi.last_entry_time)
        return self._minutes_in_range(start, open_minutes, last_entry)

    def _minutes_in_range(self, minutes: int, start: int, end: int) -> bool:
        if end >= start:
            return start <= minutes <= end
        return minutes >= start or minutes <= end

    def _parse_time(self, value: str) -> int:
        try:
            hour, minute = value.split(":", maxsplit=1)
            return int(hour) * 60 + int(minute)
        except (ValueError, AttributeError):
            return 0

    def _is_late_night(self, minutes: int) -> bool:
        hour = (minutes // 60) % 24
        return hour >= 20 or hour < 5

    def _has_context_safe_reason(self, route: Route, request: RoutePlanRequest) -> bool:
        terms = self._terms(request)
        if self._has_any(terms, ["雨天", "下雨", "室内"]) and any(stop.indoor for stop in route.stops):
            return True
        if self._has_any(terms, ["少走路", "轻松", "亲子", "老人"]) and self._travel_efficiency_score(route, request) >= 0.7:
            return True
        if self._has_any(terms, ["晚上", "夜景", "夜游"]) and route.objective == "night_friendly":
            return True
        return False

    def _poi_risk_text(self, poi: POI) -> str:
        return " ".join([*poi.negative_tags, *poi.risk_flags, *poi.avoid_reasons, *poi.tags]).lower()

    def _terms(self, request: RoutePlanRequest) -> set[str]:
        values = [
            *request.intent.preferences,
            *request.user_profile.preferences,
            *request.user_profile.tags,
            *[tag.tag for tag in request.strategy_tags],
        ]
        return set(self._terms_from_values(values))

    def _terms_from_values(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _has_any(self, terms: set[str], values: list[str]) -> bool:
        return any(value in term or term in value for term in terms for value in values)

    def _clip(self, value: float) -> float:
        return max(0.0, min(1.0, value))
