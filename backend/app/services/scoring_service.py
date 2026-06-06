import math

from app.schemas.poi import POI
from app.schemas.route import RoutePlanRequest, RouteScoreBreakdown, RouteStop
from app.schemas.user import StrategyWeights


class ScoringService:
    """B-owned module: explainable score rules for route comparison."""

    OBJECTIVE_WEIGHTS = {
        "balanced": StrategyWeights(quality=0.30, queue=0.25, distance=0.20, budget=0.15, preference=0.10),
        "low_queue": StrategyWeights(quality=0.20, queue=0.45, distance=0.15, budget=0.10, preference=0.10),
        "budget": StrategyWeights(quality=0.20, queue=0.15, distance=0.10, budget=0.45, preference=0.10),
        "low_walking": StrategyWeights(quality=0.15, queue=0.20, distance=0.45, budget=0.10, preference=0.10),
        "food_first": StrategyWeights(quality=0.30, queue=0.15, distance=0.10, budget=0.10, preference=0.35),
        "photo_food": StrategyWeights(quality=0.30, queue=0.12, distance=0.10, budget=0.08, preference=0.40),
        "nature_relax": StrategyWeights(quality=0.22, queue=0.14, distance=0.24, budget=0.10, preference=0.30),
        "photo_citywalk": StrategyWeights(quality=0.20, queue=0.15, distance=0.20, budget=0.10, preference=0.35),
        "indoor_rainy": StrategyWeights(quality=0.15, queue=0.15, distance=0.20, budget=0.10, preference=0.40),
        "night_friendly": StrategyWeights(quality=0.25, queue=0.15, distance=0.15, budget=0.10, preference=0.35),
    }

    def score(
        self,
        stops: list[RouteStop],
        objective: str,
        request: RoutePlanRequest,
        poi_by_id: dict[str, POI],
    ) -> RouteScoreBreakdown:
        pois = self._pois_for_stops(stops, poi_by_id)
        if not stops:
            return RouteScoreBreakdown(quality=0, queue=0, budget=0, distance=0, preference=0)
        return RouteScoreBreakdown(
            quality=self._quality_score(stops, pois),
            queue=self._queue_score(stops, pois),
            budget=self._budget_score(stops, pois, request.intent.budget_per_person),
            distance=self._distance_score(stops, pois),
            preference=self._preference_score(stops, pois, objective, request),
        )

    def overall_score(
        self,
        breakdown: RouteScoreBreakdown,
        objective: str,
        stops: list[RouteStop],
        request: RoutePlanRequest,
        poi_by_id: dict[str, POI],
    ) -> int:
        weights = self.OBJECTIVE_WEIGHTS.get(objective, self._normalized_weights(request.strategy_weights))
        weighted = (
            breakdown.quality * weights.quality
            + breakdown.queue * weights.queue
            + breakdown.distance * weights.distance
            + breakdown.budget * weights.budget
            + breakdown.preference * weights.preference
        )
        return self._clamp(round(weighted - self.hard_penalty(stops, objective, request, poi_by_id)), minimum=0)

    def hard_penalty(
        self,
        stops: list[RouteStop],
        objective: str,
        request: RoutePlanRequest,
        poi_by_id: dict[str, POI],
    ) -> int:
        penalty = 0
        total_queue = sum(stop.queue_minutes for stop in stops)
        total_cost = sum(stop.estimated_cost for stop in stops)
        time_limit = max(60, request.intent.duration_hours * 60)
        total_duration = self._route_elapsed_minutes(request.intent.start_time, stops)
        pois = self._pois_for_stops(stops, poi_by_id)

        if total_duration > time_limit:
            penalty += min(35, math.ceil((total_duration - time_limit) / 10) * 5)

        budget = max(request.intent.budget_per_person, 1)
        if total_cost > budget:
            penalty += min(30, math.ceil(((total_cost - budget) / budget) * 20))
        if total_cost > budget * 1.5:
            penalty += 15

        penalty += sum(12 for stop in stops if not self._is_open_for_stop(stop, poi_by_id.get(stop.poi_id)))

        avoid_terms = self._terms([*request.intent.avoid_tags, *request.user_profile.avoid_tags])
        for poi in pois:
            risk_text = self._poi_risk_text(poi)
            if any(self._term_matches(term, risk_text) for term in avoid_terms):
                penalty += 18

        if objective == "food_first" and not any(self._is_food_poi(stop, poi_by_id.get(stop.poi_id)) for stop in stops):
            penalty += 25
        if objective == "photo_food" and not any(self._is_food_poi(stop, poi_by_id.get(stop.poi_id)) and "photo_stop" in stop.route_roles for stop in stops):
            penalty += 18
        if objective == "nature_relax" and not any(self._nature_stop_score(stop, poi_by_id.get(stop.poi_id)) > 0 for stop in stops):
            penalty += 18
        if objective == "indoor_rainy" and not any((poi_by_id.get(stop.poi_id) and poi_by_id[stop.poi_id].indoor) or stop.indoor for stop in stops):
            penalty += 25

        penalty += self._structure_penalty(stops, objective, request)
        return min(70, penalty)

    def preference_match_ratio(self, stops: list[RouteStop], request: RoutePlanRequest, poi_by_id: dict[str, POI]) -> float:
        terms = self._preference_terms(request)
        if not terms:
            return 0
        route_text = self._route_text(stops, self._pois_for_stops(stops, poi_by_id))
        matches = sum(1 for term in terms if self._term_matches(term, route_text))
        return matches / len(terms)

    def _quality_score(self, stops: list[RouteStop], pois: list[POI]) -> int:
        if not pois:
            fallback_hits = sum(1 for stop in stops if any(tag in stop.tags for tag in ["经典", "文艺", "夜景", "互动体验", "小众"]))
            return self._clamp(70 + fallback_hits * 5)

        weighted_sum = 0.0
        total_weight = 0
        risk_penalty = 0
        for poi in pois:
            rating_score = self._clamp_float((poi.rating - 3.5) / 1.5)
            review_score = min(math.log10(max(poi.review_count, 0) + 1) / 4, 1)
            poi_quality = rating_score * 0.55 + self._clamp_float(poi.popularity) * 0.25 + review_score * 0.20
            weight = max(poi.visit_duration_minutes, 30)
            weighted_sum += poi_quality * weight
            total_weight += weight
            if poi.risk_flags:
                risk_penalty += 2
            if poi.need_booking:
                risk_penalty += 1
        return self._clamp(round((weighted_sum / max(total_weight, 1)) * 100 - risk_penalty))

    def _queue_score(self, stops: list[RouteStop], pois: list[POI]) -> int:
        total_queue = sum(stop.queue_minutes for stop in stops)
        if pois:
            live_levels = [poi.live_crowd_level if poi.live_crowd_level > 0 else poi.crowd_level for poi in pois]
            avg_live_crowd = sum(live_levels) / len(live_levels)
            avg_crowd = sum(poi.crowd_level for poi in pois) / len(pois)
        else:
            avg_live_crowd = 0
            avg_crowd = 0
        return self._clamp(round(100 - total_queue * 1.2 - avg_live_crowd * 25 - avg_crowd * 15))

    def _budget_score(self, stops: list[RouteStop], pois: list[POI], budget_per_person: int) -> int:
        total_cost = sum(stop.estimated_cost for stop in stops)
        budget = max(budget_per_person, 1)
        if total_cost <= budget:
            score = 85 + 15 * (1 - total_cost / budget)
        else:
            score = 85 - ((total_cost - budget) / budget) * 80
        if pois:
            score += (sum(poi.budget_friendly for poi in pois) / len(pois)) * 5
        return self._clamp(round(score))

    def _distance_score(self, stops: list[RouteStop], pois: list[POI]) -> int:
        total_distance = sum(stop.distance_km_from_previous or 0 for stop in stops)
        total_travel = sum(stop.travel_minutes_from_previous or 0 for stop in stops)
        walking_penalty = sum({"low": 0, "medium": 5, "high": 15}.get(stop.walking_intensity, 7) for stop in stops)
        transit_bonus = sum(1 for poi in pois if poi.transit_hub_nearby or "metro" in poi.recommended_transport) * 2
        repeated_category_penalty = sum(
            5 for previous, current in zip(stops, stops[1:]) if previous.primary_category and previous.primary_category == current.primary_category
        )
        return self._clamp(round(100 - total_distance * 5 - total_travel * 0.7 - walking_penalty + transit_bonus - repeated_category_penalty))

    def _preference_score(self, stops: list[RouteStop], pois: list[POI], objective: str, request: RoutePlanRequest) -> int:
        user_match = self.preference_match_ratio(stops, request, {poi.id: poi for poi in pois})
        objective_fit = self._objective_fit(stops, pois, objective, request)
        structure_fit = self._structure_fit(stops, objective, request)
        return self._clamp(round(user_match * 45 + objective_fit * 35 + structure_fit * 20))

    def _objective_fit(self, stops: list[RouteStop], pois: list[POI], objective: str, request: RoutePlanRequest) -> float:
        if not stops:
            return 0
        if objective == "balanced":
            return self._structure_fit(stops, objective, request)
        if objective == "low_queue":
            return self._queue_score(stops, pois) / 100
        if objective == "budget":
            return self._budget_score(stops, pois, request.intent.budget_per_person) / 100
        if objective == "low_walking":
            low_count = sum(1 for stop in stops if stop.walking_intensity == "low")
            transit_count = sum(1 for poi in pois if poi.transit_hub_nearby or "metro" in poi.recommended_transport)
            return min(1, low_count / len(stops) * 0.7 + transit_count / max(len(stops), 1) * 0.3)
        if objective == "food_first":
            meal_count = sum(1 for stop in stops if "meal" in stop.route_roles)
            foodish_count = sum(1 for stop in stops if self._is_food_poi(stop, next((poi for poi in pois if poi.id == stop.poi_id), None)))
            return min(1, meal_count / max(len(stops), 1) * 0.55 + foodish_count / max(len(stops), 1) * 0.3 + self._structure_fit(stops, objective, request) * 0.15)
        if objective == "photo_food":
            food_photo_count = sum(
                1
                for stop in stops
                if self._is_food_poi(stop, next((poi for poi in pois if poi.id == stop.poi_id), None)) and self._photo_stop_score(stop, next((poi for poi in pois if poi.id == stop.poi_id), None)) > 0
            )
            return min(1, food_photo_count / max(len(stops), 1) * 0.7 + self._structure_fit(stops, objective, request) * 0.3)
        if objective == "nature_relax":
            nature_count = sum(1 for stop in stops if self._nature_stop_score(stop, next((poi for poi in pois if poi.id == stop.poi_id), None)) > 0)
            low_count = sum(1 for stop in stops if stop.walking_intensity == "low")
            return min(1, nature_count / max(len(stops), 1) * 0.7 + low_count / max(len(stops), 1) * 0.2 + self._structure_fit(stops, objective, request) * 0.1)
        if objective == "photo_citywalk":
            photo_count = sum(1 for stop in stops if "photo_stop" in stop.route_roles)
            return min(1, photo_count / max(len(stops), 1) * 0.65 + self._structure_fit(stops, objective, request) * 0.35)
        if objective == "indoor_rainy":
            indoor_main = sum(1 for stop in stops if stop.indoor and "main_activity" in stop.route_roles)
            indoor_ratio = sum(1 for stop in stops if stop.indoor) / max(len(stops), 1)
            return min(1, indoor_main / max(len(stops), 1) * 0.55 + indoor_ratio * 0.3 + self._structure_fit(stops, objective, request) * 0.15)
        if objective == "night_friendly":
            night_avg = sum(poi.night_activity for poi in pois) / max(len(pois), 1)
            slot_ratio = sum(1 for poi in pois if {"evening", "night"} & set(poi.suitable_time_slots)) / max(len(stops), 1)
            return min(1, night_avg * 0.65 + slot_ratio * 0.35)
        return 0

    def _structure_fit(self, stops: list[RouteStop], objective: str, request: RoutePlanRequest) -> float:
        if not stops:
            return 0
        role_counts = self._role_counts(stops)
        score = 0.0
        if role_counts.get("main_activity", 0) >= 1:
            score += 0.4
        if role_counts.get("meal", 0) >= 1 or role_counts.get("snack", 0) >= 1:
            score += 0.2
        if role_counts.get("coffee_break", 0) <= 1 or self._allows_repeated_coffee(request):
            score += 0.15
        if role_counts.get("photo_stop", 0) >= 1:
            score += 0.15
        if role_counts.get("rest_stop", 0) >= 1:
            score += 0.1
        if objective == "photo_citywalk" and role_counts.get("photo_stop", 0) == 0:
            score -= 0.25
        if objective == "indoor_rainy" and not any(stop.indoor and "main_activity" in stop.route_roles for stop in stops):
            score -= 0.25
        return self._clamp_float(score)

    def _structure_penalty(self, stops: list[RouteStop], objective: str, request: RoutePlanRequest) -> int:
        role_counts = self._role_counts(stops)
        primary_counts: dict[str, int] = {}
        for stop in stops:
            primary_counts[stop.primary_category] = primary_counts.get(stop.primary_category, 0) + 1

        penalty = 0
        if role_counts.get("main_activity", 0) == 0:
            penalty += 18
        if role_counts.get("coffee_break", 0) > 1 and not self._allows_repeated_coffee(request):
            penalty += 14 * (role_counts["coffee_break"] - 1)
        if role_counts.get("meal", 0) > 1 and not self._allows_repeated_meals(request):
            penalty += 10 * (role_counts["meal"] - 1)
        for count in primary_counts.values():
            if count > 2:
                penalty += 6 * (count - 2)
        for previous, current in zip(stops, stops[1:]):
            if previous.primary_category and previous.primary_category == current.primary_category:
                penalty += 5
            if set(previous.route_roles) & set(current.route_roles):
                penalty += 3
        if objective == "photo_citywalk" and role_counts.get("photo_stop", 0) == 0:
            penalty += 16
        if objective == "indoor_rainy" and not any(stop.indoor and "main_activity" in stop.route_roles for stop in stops):
            penalty += 16
        if objective == "food_first" and role_counts.get("meal", 0) == 0:
            penalty += 12
        if objective == "photo_food" and not any(self._is_food_poi(stop, None) and "photo_stop" in stop.route_roles for stop in stops):
            penalty += 14
        if objective == "nature_relax" and not any(self._nature_stop_score(stop, None) > 0 for stop in stops):
            penalty += 14
        return penalty

    def _role_counts(self, stops: list[RouteStop]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for stop in stops:
            for role in stop.route_roles:
                counts[role] = counts.get(role, 0) + 1
        return counts

    def _normalized_weights(self, weights: StrategyWeights) -> StrategyWeights:
        total = weights.quality + weights.queue + weights.distance + weights.budget + weights.preference
        if total <= 0:
            return self.OBJECTIVE_WEIGHTS["balanced"]
        return StrategyWeights(
            quality=weights.quality / total,
            queue=weights.queue / total,
            distance=weights.distance / total,
            budget=weights.budget / total,
            preference=weights.preference / total,
        )

    def _pois_for_stops(self, stops: list[RouteStop], poi_by_id: dict[str, POI]) -> list[POI]:
        return [poi_by_id[stop.poi_id] for stop in stops if stop.poi_id in poi_by_id]

    def _preference_terms(self, request: RoutePlanRequest) -> list[str]:
        return self._terms(
            [
                *request.intent.interest_tags,
                *request.intent.optimization_goals,
                *request.intent.preferences,
                *request.user_profile.interest_tags,
                *request.user_profile.optimization_goals,
                *request.user_profile.preferences,
                *request.user_profile.tags,
                *[tag.tag for tag in request.strategy_tags],
            ]
        )

    def _photo_stop_score(self, stop: RouteStop, poi: POI | None) -> float:
        text = self._stop_text(stop, poi)
        return 1.0 if any(term in text for term in ["拍照", "出片", "好看", "文艺", "经典", "环境", "photo"]) else 0.0

    def _nature_stop_score(self, stop: RouteStop, poi: POI | None) -> float:
        text = self._stop_text(stop, poi)
        return 1.0 if stop.category == "park" or any(term in text for term in ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"]) else 0.0

    def _stop_text(self, stop: RouteStop, poi: POI | None) -> str:
        parts = [
            stop.name,
            stop.category,
            stop.primary_category,
            stop.meal_type,
            stop.highlight_text,
            stop.ugc_tip,
            *stop.secondary_categories,
            *stop.route_roles,
            *stop.experience_tags,
            *stop.tags,
        ]
        if poi:
            parts.extend([poi.name, poi.highlight_text, poi.ugc_tip, *poi.tags, *poi.highlight_text_tags, *poi.experience_tags])
        return " ".join(str(part) for part in parts if part)

    def _terms(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _route_text(self, stops: list[RouteStop], pois: list[POI]) -> str:
        parts: list[str] = []
        for stop in stops:
            parts.extend(
                [
                    stop.name,
                    stop.category,
                    stop.primary_category,
                    stop.meal_type,
                    stop.walking_intensity,
                    stop.highlight_text,
                    stop.ugc_tip,
                    *stop.secondary_categories,
                    *stop.route_roles,
                    *stop.experience_tags,
                    *stop.tags,
                ]
            )
        for poi in pois:
            parts.extend(
                [
                    poi.name,
                    poi.category,
                    poi.primary_category,
                    poi.meal_type,
                    poi.highlight_text,
                    poi.ugc_tip,
                    poi.walking_intensity,
                    *poi.secondary_categories,
                    *poi.route_roles,
                    *poi.experience_tags,
                    *poi.tags,
                    *poi.highlight_text_tags,
                    *poi.suitable_time_slots,
                ]
            )
        return " ".join(str(part) for part in parts if part).lower()

    def _poi_risk_text(self, poi: POI) -> str:
        return " ".join([*poi.negative_tags, *poi.risk_flags, *poi.avoid_reasons, *poi.tags]).lower()

    def _term_matches(self, term: str, text: str) -> bool:
        aliases = {
            "少排队": ["少排队", "别排队", "不排队", "排队可接受", "低排队", "queue"],
            "美食": ["吃好", "美食", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining", "meal"],
            "吃好": ["吃好", "美食", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining", "meal"],
            "food_first": ["吃好", "美食", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining", "meal"],
            "photo_food": ["拍照", "出片", "好看", "环境", "餐厅", "美食", "restaurant", "photo"],
            "nature": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "nature_relax": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "咖啡": ["咖啡", "下午茶", "休息", "cafe", "coffee_break"],
            "轻食": ["轻食", "小吃", "light_meal", "fast_food", "market", "snack"],
            "小吃": ["小吃", "轻食", "light_meal", "fast_food", "market", "snack"],
            "更省钱": ["省钱", "便宜", "免费", "budget"],
            "省钱": ["省钱", "便宜", "免费", "budget"],
            "便宜": ["省钱", "便宜", "免费", "budget"],
            "少走路": ["少走路", "轻松", "交通", "metro", "low", "transit_anchor"],
            "low_walking": ["少走路", "轻松", "交通", "metro", "low", "transit_anchor"],
            "轻松": ["少走路", "轻松", "low", "metro"],
            "citywalk": ["citywalk", "街区", "散步", "漫步", "拍照", "landmark", "photo_stop"],
            "室内": ["室内", "雨天", "museum", "gallery", "theater", "cafe", "shopping", "indoor"],
            "indoor_rainy": ["室内", "雨天", "museum", "gallery", "theater", "cafe", "shopping", "indoor"],
            "雨天": ["雨天", "室内", "museum", "gallery", "theater", "cafe", "shopping", "rainy"],
            "拍照": ["拍照", "夜景", "出片", "photo", "photo_stop"],
            "photo": ["拍照", "夜景", "出片", "photo", "photo_stop"],
            "晚上": ["晚上", "夜景", "夜游", "evening", "night", "night_view", "night_end"],
            "night_view": ["晚上", "夜景", "夜游", "evening", "night", "night_view", "night_end"],
            "人多": ["人多", "人流密集", "拥挤", "crowded"],
            "人流密集": ["人流密集", "拥挤", "人多", "long_queue"],
            "排队久": ["排队久", "long_queue", "排队"],
            "太贵": ["太贵", "高价", "贵"],
        }
        lowered = text.lower()
        return any(value.lower() in lowered for value in aliases.get(term, [term]))

    def _has_any(self, terms: set[str], values: list[str]) -> bool:
        return any(value in term or term in value for term in terms for value in values)

    def _is_food_poi(self, stop: RouteStop, poi: POI | None) -> bool:
        if stop.category in {"restaurant", "cafe", "market"} or stop.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}:
            return True
        return bool(poi and (poi.category in {"restaurant", "cafe", "market"} or poi.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}))

    def _is_open_for_stop(self, stop: RouteStop, poi: POI | None) -> bool:
        if poi is None:
            return True
        start = self._parse_time(stop.start_time)
        return self._minutes_in_range(start, self._parse_time(poi.open_time), self._parse_time(poi.last_entry_time))

    def _route_elapsed_minutes(self, start_time: str, stops: list[RouteStop]) -> int:
        if not stops:
            return 0
        start = self._parse_time(start_time)
        end = self._parse_time(stops[-1].end_time)
        if end < start:
            end += 24 * 60
        return end - start

    def _parse_time(self, value: str) -> int:
        try:
            hour, minute = value.split(":", maxsplit=1)
            return int(hour) * 60 + int(minute)
        except (ValueError, AttributeError):
            return 0

    def _minutes_in_range(self, minutes: int, start: int, end: int) -> bool:
        if end >= start:
            return start <= minutes <= end
        return minutes >= start or minutes <= end

    def _allows_repeated_coffee(self, request: RoutePlanRequest) -> bool:
        terms = set(self._preference_terms(request))
        return self._has_any(terms, ["咖啡探店", "咖啡路线", "多家咖啡", "咖啡馆"])

    def _allows_repeated_meals(self, request: RoutePlanRequest) -> bool:
        terms = set(self._preference_terms(request))
        return self._has_any(terms, ["美食路线", "扫街", "吃很多家", "小吃街", "多家餐厅"])

    def _clamp(self, value: int | float, minimum: int = 0) -> int:
        return max(minimum, min(100, int(round(value))))

    def _clamp_float(self, value: float) -> float:
        return max(0, min(1, value))
