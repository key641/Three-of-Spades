from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RouteStop


@dataclass
class ConstraintResult:
    feasible: bool = True
    hard_violations: list[str] = field(default_factory=list)
    soft_penalties: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def penalty(self) -> float:
        return sum(self.soft_penalties.values())


class ConstraintEvaluator:
    """Single source of truth for route feasibility and explainable soft risks."""

    EXTREME_BUDGET_MULTIPLIER = 2.0

    def evaluate_poi(
        self,
        poi: POI,
        request: RoutePlanRequest,
        arrival_minutes: int,
        elapsed_after_minutes: int,
        cumulative_cost: int,
        selected: list[POI] | None = None,
        distance_km: float | None = None,
    ) -> ConstraintResult:
        result = ConstraintResult()
        intent = request.intent
        if poi.city != intent.city:
            result.hard_violations.append("city_mismatch")
        if intent.target_district and intent.target_district not in f"{poi.district} {poi.address}":
            result.hard_violations.append("district_mismatch")
        if intent.target_business_area and intent.target_business_area not in f"{poi.business_area} {poi.address}":
            result.hard_violations.append("business_area_mismatch")
        if elapsed_after_minutes > self._effective_duration_limit(intent.duration_hours):
            result.hard_violations.append("duration_exceeded")
        if not self._in_window(arrival_minutes, self._parse_time(poi.open_time), self._parse_time(poi.last_entry_time)):
            result.hard_violations.append("closed_at_arrival")

        avoid_terms = self._terms([*intent.avoid_tags, *request.user_profile.avoid_tags])
        risk_text = " ".join([*poi.negative_tags, *poi.risk_flags, *poi.avoid_reasons, *poi.tags]).lower()
        if any(term in risk_text for term in avoid_terms):
            result.hard_violations.append("avoid_tag_match")

        budget = max(intent.budget_per_person, 1)
        if cumulative_cost > max(budget * self.EXTREME_BUDGET_MULTIPLIER, budget + 160):
            result.hard_violations.append("extreme_budget_exceeded")
        elif cumulative_cost > budget:
            result.soft_penalties["budget_over"] = min(20.0, (cumulative_cost - budget) / budget * 20)
            result.warnings.append("预计费用略高于预算")

        terms = set(self._terms([*intent.preferences, *intent.interest_tags, *intent.optimization_goals]))
        low_energy = self._has_any(terms, {"少走路", "轻松", "老人", "亲子"}) or request.user_profile.walking_tolerance <= 0.35
        rainy_or_hot = self._has_any(terms, {"雨天", "下雨", "室内", "高温", "避暑"})
        if distance_km is not None and distance_km > 1 and low_energy:
            result.soft_penalties["long_walk"] = min(16.0, distance_km * 4)
            result.warnings.append("存在较长移动路段")
        if poi.queue_minutes >= 35 and request.user_profile.crowd_tolerance <= 0.4:
            result.soft_penalties["crowded"] = min(15.0, poi.queue_minutes / 4)
            result.warnings.append("部分地点排队风险较高")
        if rainy_or_hot and not poi.indoor and poi.walking_intensity == "high":
            result.soft_penalties["weather_exposure"] = 12.0
            result.warnings.append("天气条件下户外强度较高")
        if poi.need_booking:
            result.soft_penalties["booking_required"] = 3.0
            result.warnings.append("包含需要预约的地点")
        if ("meal" in poi.route_roles or poi.category == "restaurant") and not self._meal_window_fit(arrival_minutes):
            result.soft_penalties["meal_time_mismatch"] = 8.0
            result.warnings.append("正餐时间与常规用餐时段存在偏差")

        selected = selected or []
        if selected:
            previous = selected[-1]
            if previous.primary_category == poi.primary_category:
                result.soft_penalties["repeated_category"] = 5.0
            if previous.business_area and poi.business_area and previous.business_area != poi.business_area and (distance_km or 0) > 5:
                result.soft_penalties["cross_area_jump"] = 8.0
        result.feasible = not result.hard_violations
        result.warnings = list(dict.fromkeys(result.warnings))
        return result

    def evaluate_route(self, route: Route, request: RoutePlanRequest, poi_by_id: dict[str, POI]) -> ConstraintResult:
        result = ConstraintResult()
        route_ids = {stop.poi_id for stop in route.stops}
        missing_required = set(request.intent.must_include_poi_ids) - route_ids
        if missing_required:
            result.hard_violations.extend(f"missing_required:{poi_id}" for poi_id in sorted(missing_required))
        for role in request.intent.must_include_roles:
            if not self._route_satisfies_role(route, role):
                result.hard_violations.append(f"missing_required_role:{role}")
        if route.total_duration_minutes > self._effective_duration_limit(request.intent.duration_hours):
            result.hard_violations.append("duration_exceeded")
        budget = max(request.intent.budget_per_person, 1)
        if route.total_cost_per_person > max(budget * self.EXTREME_BUDGET_MULTIPLIER, budget + 160):
            result.hard_violations.append("extreme_budget_exceeded")
        elif route.total_cost_per_person > budget:
            result.soft_penalties["budget_over"] = min(20.0, (route.total_cost_per_person - budget) / budget * 20)
            result.warnings.append("预计费用略高于预算")

        high_intensity_streak = 0
        avoid_terms = self._terms([*request.intent.avoid_tags, *request.user_profile.avoid_tags])
        for stop in route.stops:
            poi = poi_by_id.get(stop.poi_id)
            if poi is None:
                continue
            if poi.city != request.intent.city:
                result.hard_violations.append(f"city_mismatch:{poi.id}")
            if request.intent.target_district and request.intent.target_district not in f"{poi.district} {poi.address}":
                result.hard_violations.append(f"district_mismatch:{poi.id}")
            if request.intent.target_business_area and request.intent.target_business_area not in f"{poi.business_area} {poi.address}":
                result.hard_violations.append(f"business_area_mismatch:{poi.id}")
            risk_text = " ".join([*poi.negative_tags, *poi.risk_flags, *poi.avoid_reasons, *poi.tags]).lower()
            if any(term in risk_text for term in avoid_terms):
                result.hard_violations.append(f"avoid_tag_match:{poi.id}")
            if not self._in_window(self._parse_time(stop.start_time), self._parse_time(poi.open_time), self._parse_time(poi.last_entry_time)):
                result.hard_violations.append(f"closed_at_arrival:{poi.id}")
            high_intensity_streak = high_intensity_streak + 1 if stop.walking_intensity == "high" else 0
            if high_intensity_streak >= 2:
                result.soft_penalties["consecutive_high_intensity"] = 10.0
                result.warnings.append("连续高强度活动较多")
        result.feasible = not result.hard_violations
        result.warnings = list(dict.fromkeys(result.warnings))
        return result

    def reliability(self, route: Route, request: RoutePlanRequest, result: ConstraintResult) -> tuple[int, int, float, str]:
        base = route.total_duration_minutes
        uncertainty = round(route.total_travel_minutes * 0.20 + route.total_queue_minutes * 0.35)
        if any(stop.need_booking for stop in route.stops):
            uncertainty += 8
        p80 = base + uncertainty
        limit = self._effective_duration_limit(request.intent.duration_hours)
        buffer_minutes = max(0, limit - p80)
        risk = min(1.0, result.penalty / 50 + max(0, p80 - limit) / max(limit, 1))
        reliability = round(max(0.0, min(1.0, 1 - risk)), 2)
        risk_level = "low" if reliability >= 0.8 else "medium" if reliability >= 0.6 else "high"
        return p80, buffer_minutes, reliability, risk_level

    def _parse_time(self, value: str) -> int:
        try:
            hour, minute = value.split(":", maxsplit=1)
            return int(hour) * 60 + int(minute)
        except (ValueError, AttributeError):
            return 0

    def _effective_duration_limit(self, duration_hours: int) -> int:
        """Keep feasibility aligned with the planner's minimum-stop compatibility window."""
        if duration_hours <= 2:
            minimum_stops = 2
        elif duration_hours <= 6:
            minimum_stops = 3
        else:
            minimum_stops = 4
        return max(60, duration_hours * 60, minimum_stops * 100)

    def _in_window(self, value: int, start: int, end: int) -> bool:
        if end >= start:
            return start <= value <= end
        return value >= start or value <= end

    def _meal_window_fit(self, minutes: int) -> bool:
        minute_of_day = minutes % (24 * 60)
        return 11 * 60 <= minute_of_day <= 14 * 60 + 30 or 17 * 60 <= minute_of_day <= 21 * 60 + 30

    def _route_satisfies_role(self, route: Route, role: str) -> bool:
        aliases = {
            "meal_stop": {"meal", "snack"},
            "rest_stop": {"rest_stop", "coffee_break"},
        }
        accepted = aliases.get(role, {role})
        return any(accepted & set(stop.route_roles) for stop in route.stops)

    def _terms(self, values: list[str]) -> list[str]:
        return [str(value).strip().lower() for value in values if str(value).strip()]

    def _has_any(self, terms: set[str], values: set[str]) -> bool:
        return any(left in right or right in left for left in terms for right in values)
