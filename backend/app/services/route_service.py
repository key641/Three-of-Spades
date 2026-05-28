import math
import re
from dataclasses import dataclass

from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RoutePlanResponse, RouteScoreBreakdown, RouteStop
from app.services.amap_service import AmapService, GeoPoint, RouteLeg
from app.services.scoring_service import ScoringService
from app.services.strategy_service import StrategyService


@dataclass(frozen=True)
class RouteBuildState:
    current_minutes: int
    elapsed_minutes: int
    current_lat: float | None
    current_lng: float | None


class RouteService:
    """B-owned module: creates route candidates before final scoring."""

    OBJECTIVE_TITLES = {
        "balanced": "综合候选路线",
        "budget": "省钱候选路线",
        "low_walking": "少走路候选路线",
        "food_first": "吃好优先候选路线",
        "photo_food": "拍照餐饮候选路线",
        "nature_relax": "自然风景候选路线",
        "photo_citywalk": "拍照 Citywalk 候选路线",
        "indoor_rainy": "室内雨天候选路线",
        "night_friendly": "夜间友好候选路线",
    }

    CANDIDATES_PER_OBJECTIVE = 4

    def __init__(self, amap_service: AmapService | None = None) -> None:
        self.amap_service = amap_service or AmapService()
        self.scoring_service = ScoringService()
        self.strategy_service = StrategyService()

    def generate_routes(self, request: RoutePlanRequest) -> RoutePlanResponse:
        if not request.candidate_pois:
            return RoutePlanResponse(routes=[])

        objectives = self._select_objectives(request)
        routes: list[Route] = []
        poi_by_id = {poi.id: poi for poi in request.candidate_pois}

        for objective in objectives:
            candidates = self._build_candidates_for_objective(request.candidate_pois, objective, request)
            scored_candidates = self._score_candidates(candidates, objective, request, poi_by_id)
            if not scored_candidates:
                continue
            selected = scored_candidates[0]
            selected.route_id = f"route_{objective}_best"
            selected.title = self.OBJECTIVE_TITLES[objective].replace("候选路线", "推荐路线")
            selected.summary = self._summary(
                objective,
                len(selected.stops),
                selected.total_cost_per_person,
                selected.total_queue_minutes,
                selected.total_travel_minutes,
                selected.score,
                selected.score_breakdown,
            )
            selected.reasons = self._reasons(
                objective,
                selected.stops,
                selected.total_cost_per_person,
                selected.total_queue_minutes,
                selected.total_distance_km,
                selected.score_breakdown,
            )
            routes.append(selected)

        return RoutePlanResponse(routes=routes)

    def _score_candidates(
        self,
        candidates: list[Route],
        objective: str,
        request: RoutePlanRequest,
        poi_by_id: dict[str, POI],
    ) -> list[Route]:
        scored: list[Route] = []
        for route in candidates:
            if not route.stops:
                continue
            route.score_breakdown = self.scoring_service.score(route.stops, objective, request, poi_by_id)
            route.score = self.scoring_service.overall_score(route.score_breakdown, objective, route.stops, request, poi_by_id)
            scored.append(route)
        return sorted(scored, key=lambda route: self._route_rank_key(route, objective, request, poi_by_id), reverse=True)

    def _route_rank_key(self, route: Route, objective: str, request: RoutePlanRequest, poi_by_id: dict[str, POI]) -> tuple[float, float, float, float, float, float]:
        ideal_stops = sum(self._stop_bounds(request)) / 2
        stop_fit = -abs(len(route.stops) - ideal_stops)
        time_fit = -abs(route.total_duration_minutes - request.intent.duration_hours * 60 * 0.85)
        preference_fit = self.scoring_service.preference_match_ratio(route.stops, request, poi_by_id)
        objective_fit = {
            "budget": -route.total_cost_per_person,
            "low_walking": -route.total_distance_km,
            "food_first": route.score_breakdown.preference,
            "photo_food": route.score_breakdown.preference,
            "nature_relax": route.score_breakdown.preference,
            "photo_citywalk": route.score_breakdown.preference,
            "indoor_rainy": route.score_breakdown.preference,
            "night_friendly": route.score_breakdown.preference,
        }.get(objective, route.score_breakdown.preference)
        return (route.score, objective_fit, stop_fit, time_fit, -route.total_distance_km, preference_fit)

    def _select_objectives(self, request: RoutePlanRequest) -> list[str]:
        if not request.intent.preferences and not request.user_profile.tags and not request.user_profile.preferences:
            return ["photo_citywalk", "food_first", "balanced"]

        data_counts = self._objective_data_counts(request.candidate_pois)
        scores = self.strategy_service.objective_scores(request.strategy_tags, request.user_profile, data_counts)
        ordered = [objective for objective, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if objective != "balanced" and score > 0]
        selected = ordered[:2]
        if "balanced" not in selected:
            selected.append("balanced")
        for fallback in ["food_first", "photo_citywalk", "nature_relax", "indoor_rainy", "low_walking", "budget", "night_friendly"]:
            if len(selected) >= 3:
                break
            if fallback not in selected:
                selected.append(fallback)
        return selected[:3]

    def _build_candidates_for_objective(self, pois: list[POI], objective: str, request: RoutePlanRequest) -> list[Route]:
        time_limit = max(60, request.intent.duration_hours * 60)
        min_stops, max_stops = self._stop_bounds(request)
        start_pool = self._start_candidates(pois, objective, request)
        routes: list[Route] = []

        for seed in start_pool[: self.CANDIDATES_PER_OBJECTIVE * 2]:
            route = self._build_candidate(seed, pois, objective, request, time_limit, min_stops, max_stops)
            if route.stops and len(route.stops) >= min_stops:
                routes.append(route)
            if len(routes) >= self.CANDIDATES_PER_OBJECTIVE:
                break

        if len(routes) < self.CANDIDATES_PER_OBJECTIVE:
            for seed in start_pool[self.CANDIDATES_PER_OBJECTIVE * 2 :]:
                route = self._build_candidate(seed, pois, objective, request, time_limit, 1, max_stops)
                if route.stops:
                    routes.append(route)
                if len(routes) >= self.CANDIDATES_PER_OBJECTIVE:
                    break

        return routes

    def _build_candidate(
        self,
        seed: POI,
        pois: list[POI],
        objective: str,
        request: RoutePlanRequest,
        time_limit: int,
        min_stops: int,
        max_stops: int,
    ) -> Route:
        state = RouteBuildState(
            current_minutes=self._parse_time(request.intent.start_time),
            elapsed_minutes=0,
            current_lat=request.intent.start_lat,
            current_lng=request.intent.start_lng,
        )
        stops: list[RouteStop] = []
        selected_ids: set[str] = set()

        first = self._append_if_feasible(seed, state, time_limit, objective, request)
        if first is None:
            return self._route_from_stops([], objective, request)
        stop, state = first
        stops.append(stop)
        selected_ids.add(seed.id)

        required_food = self._route_wants_food(objective, request)
        while len(stops) < max_stops:
            next_poi = self._next_poi(pois, selected_ids, objective, request, state, time_limit, required_food, len(stops) < min_stops)
            if next_poi is None:
                break
            appended = self._append_if_feasible(next_poi, state, time_limit, objective, request)
            if appended is None:
                selected_ids.add(next_poi.id)
                continue
            stop, state = appended
            stops.append(stop)
            selected_ids.add(next_poi.id)
            if len(stops) >= min_stops and state.elapsed_minutes >= time_limit * 0.82:
                break

        if required_food and not any(self._is_food_poi(stop) for stop in stops):
            replacement = self._food_replacement(pois, selected_ids, objective, request, state, time_limit)
            if replacement is not None:
                appended = self._append_if_feasible(replacement, state, time_limit, objective, request)
                if appended is not None and len(stops) < max_stops:
                    stop, state = appended
                    stops.append(stop)

        return self._route_from_stops(stops, objective, request)

    def _append_if_feasible(
        self,
        poi: POI,
        state: RouteBuildState,
        time_limit: int,
        objective: str,
        request: RoutePlanRequest,
    ) -> tuple[RouteStop, RouteBuildState] | None:
        distance = self._distance_km(state.current_lat, state.current_lng, poi)
        transport_mode = self._transport_mode(distance, poi)
        route_leg = self._route_leg(state.current_lat, state.current_lng, poi, transport_mode)
        travel_minutes = route_leg.duration_minutes if route_leg else self._travel_minutes(distance)
        distance_km = self._distance_from_leg(route_leg, distance)
        total_add = travel_minutes + poi.queue_minutes + poi.visit_duration_minutes
        if state.elapsed_minutes + total_add > time_limit:
            return None

        start_minutes = state.current_minutes + travel_minutes
        end_minutes = start_minutes + poi.queue_minutes + poi.visit_duration_minutes
        stop = RouteStop(
            poi_id=poi.id,
            name=poi.name,
            category=poi.category,
            primary_category=poi.primary_category,
            secondary_categories=poi.secondary_categories,
            route_roles=poi.route_roles,
            experience_tags=poi.experience_tags,
            district=poi.district,
            address=poi.address,
            lat=poi.lat,
            lng=poi.lng,
            start_time=self._format_time(start_minutes),
            end_time=self._format_time(end_minutes),
            estimated_cost=poi.avg_price,
            queue_minutes=poi.queue_minutes,
            tags=poi.tags,
            meal_type=poi.meal_type,
            open_hours=poi.open_hours,
            last_entry_time=poi.last_entry_time,
            walking_intensity=poi.walking_intensity,
            cover_image_url=poi.cover_image_url,
            highlight_text=poi.highlight_text,
            ugc_tip=poi.ugc_tip,
            indoor=poi.indoor,
            recommended_transport=poi.recommended_transport,
            travel_minutes_from_previous=travel_minutes if distance_km is not None else None,
            distance_km_from_previous=round(distance_km, 1) if distance_km is not None else None,
            transport_mode_from_previous=route_leg.mode if route_leg else transport_mode,
            polyline_from_previous=route_leg.polyline if route_leg else "",
            amap_distance_meters_from_previous=route_leg.distance_meters if route_leg else None,
            amap_duration_minutes_from_previous=route_leg.duration_minutes if route_leg else None,
            route_leg_source_from_previous=route_leg.source if route_leg else None,
            reason=self._stop_reason(poi, objective, request, start_minutes),
        )
        next_state = RouteBuildState(
            current_minutes=end_minutes,
            elapsed_minutes=state.elapsed_minutes + total_add,
            current_lat=poi.lat,
            current_lng=poi.lng,
        )
        return stop, next_state

    def _route_leg(self, current_lat: float | None, current_lng: float | None, poi: POI, mode: str | None) -> RouteLeg | None:
        if current_lat is None or current_lng is None or mode is None:
            return None
        return self.amap_service.route_leg(
            origin=GeoPoint(lat=current_lat, lng=current_lng),
            destination=GeoPoint(lat=poi.lat, lng=poi.lng),
            mode=mode,
        )

    def _distance_from_leg(self, route_leg: RouteLeg | None, fallback_distance: float | None) -> float | None:
        if route_leg is not None:
            return route_leg.distance_meters / 1000
        return fallback_distance

    def _route_from_stops(self, stops: list[RouteStop], objective: str, request: RoutePlanRequest) -> Route:
        total_travel = sum(stop.travel_minutes_from_previous or 0 for stop in stops)
        total_distance = round(sum(stop.distance_km_from_previous or 0 for stop in stops), 1)
        total_queue = sum(stop.queue_minutes for stop in stops)
        total_cost = sum(stop.estimated_cost for stop in stops)
        return Route(
            route_id=f"route_{objective}_candidate",
            title=self.OBJECTIVE_TITLES[objective],
            objective=objective,
            summary=self._summary(objective, len(stops), total_cost, total_queue, total_travel, 0, RouteScoreBreakdown(quality=0, queue=0, budget=0, distance=0, preference=0)),
            total_duration_minutes=self._route_elapsed_minutes(request.intent.start_time, stops),
            total_cost_per_person=total_cost,
            total_queue_minutes=total_queue,
            total_travel_minutes=total_travel,
            total_distance_km=total_distance,
            score=0,
            score_breakdown=RouteScoreBreakdown(quality=0, queue=0, budget=0, distance=0, preference=0),
            stops=stops,
            reasons=self._reasons(objective, stops, total_cost, total_queue, total_distance, RouteScoreBreakdown(quality=0, queue=0, budget=0, distance=0, preference=0)),
        )

    def _start_candidates(self, pois: list[POI], objective: str, request: RoutePlanRequest) -> list[POI]:
        return sorted(
            pois,
            key=lambda poi: self._poi_score(poi, objective, request, request.intent.start_lat, request.intent.start_lng),
            reverse=True,
        )

    def _next_poi(
        self,
        pois: list[POI],
        selected_ids: set[str],
        objective: str,
        request: RoutePlanRequest,
        state: RouteBuildState,
        time_limit: int,
        required_food: bool,
        must_extend: bool,
    ) -> POI | None:
        candidates = [poi for poi in pois if poi.id not in selected_ids]
        if required_food and not any(self._is_food_poi_id(poi_id, pois) for poi_id in selected_ids):
            food_candidates = [poi for poi in candidates if self._is_food_poi_obj(poi)]
            if food_candidates:
                candidates = food_candidates

        viable = [
            poi
            for poi in candidates
            if state.elapsed_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes
            <= time_limit
        ]
        if not viable:
            return None

        return max(
            viable,
            key=lambda poi: self._poi_score(poi, objective, request, state.current_lat, state.current_lng)
            + self._nearby_bonus(selected_ids, poi, pois)
            - self._distance_penalty(state.current_lat, state.current_lng, poi)
            - self._diversity_penalty(selected_ids, poi, pois, objective, request)
            + self._missing_role_bonus(selected_ids, poi, pois, objective, request)
            + (0.12 if must_extend else 0),
        )

    def _stop_bounds(self, request: RoutePlanRequest) -> tuple[int, int]:
        hours = request.intent.duration_hours
        if hours <= 3:
            min_stops, max_stops = 2, 3
        elif hours <= 6:
            min_stops, max_stops = 3, 4
        else:
            min_stops, max_stops = 4, 5

        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        if self._has_any(terms, ["轻松", "少走路", "老人", "亲子"]):
            max_stops = max(min_stops, max_stops - 1)
        if self._has_any(terms, ["多打卡", "citywalk", "拍照"]):
            max_stops = min(5, max_stops + 1)
        return min_stops, max_stops

    def _poi_score(self, poi: POI, objective: str, request: RoutePlanRequest, current_lat: float | None, current_lng: float | None) -> float:
        quality = self._quality_score(poi)
        queue = self._queue_score(poi)
        budget = 1 if poi.avg_price <= request.intent.budget_per_person else max(0, 1 - poi.avg_price / max(request.intent.budget_per_person * 2, 1))
        preference = self._preference_match(poi, request)
        time_fit = self._time_fit_score(poi, request)
        distance = self._distance_score(current_lat, current_lng, poi)
        walking = self._walking_score(poi)
        score = quality * 0.22 + queue * 0.14 + budget * 0.12 + preference * 0.18 + time_fit * 0.14 + distance * 0.12 + walking * 0.08

        if objective == "budget":
            score += budget * 0.5
        elif objective == "low_walking":
            score += (distance * 0.28 + walking * 0.32 + (0.15 if poi.transit_hub_nearby else 0))
        elif objective == "food_first":
            score += self._food_score(poi, request) * 0.55
        elif objective == "photo_food":
            score += self._photo_food_score(poi) * 0.65 + self._food_score(poi, request) * 0.25
        elif objective == "nature_relax":
            score += self._nature_score(poi) * 0.65 + walking * 0.12
        elif objective == "photo_citywalk":
            score += self._photo_citywalk_score(poi) * 0.55
        elif objective == "indoor_rainy":
            score += (0.35 if poi.indoor else 0) + poi.rainy_day_score * 0.25
        elif objective == "night_friendly":
            score += poi.night_activity * 0.35 + (0.2 if "night" in poi.suitable_time_slots or "evening" in poi.suitable_time_slots else 0)
        return score

    def _preference_match(self, poi: POI, request: RoutePlanRequest) -> float:
        terms = request.intent.preferences + request.user_profile.tags + request.user_profile.preferences
        if not terms:
            return 0
        return sum(1 for term in terms if self._term_matches_poi(term, poi)) / len(terms)

    def _term_matches_poi(self, term: str, poi: POI) -> bool:
        text = " ".join(
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
        ).lower()
        aliases = {
            "少排队": ["少排队", "不排队", "低排队"],
            "吃好": ["餐厅", "美食", "聚餐", "restaurant", "local_food", "fine_dining"],
            "food_first": ["餐厅", "美食", "聚餐", "restaurant", "local_food", "fine_dining"],
            "photo_food": ["拍照", "出片", "好看", "环境", "餐厅", "美食", "restaurant", "photo"],
            "nature": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "nature_relax": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "咖啡": ["咖啡", "cafe", "下午茶"],
            "citywalk": ["citywalk", "街区", "散步", "landmark", "拍照"],
            "拍照": ["拍照", "夜景", "经典", "photo"],
            "photo": ["拍照", "夜景", "经典", "photo"],
            "室内": ["室内", "museum", "gallery", "theater", "shopping", "cafe"],
            "indoor_rainy": ["室内", "museum", "gallery", "theater", "shopping", "cafe"],
            "雨天": ["室内", "雨天", "rainy"],
            "少走路": ["少走路", "轻松", "low"],
            "low_walking": ["少走路", "轻松", "low"],
            "晚上": ["晚上", "夜景", "night", "evening"],
            "night_view": ["晚上", "夜景", "night", "evening"],
        }
        return any(value.lower() in text for value in aliases.get(term, [term]))

    def _quality_score(self, poi: POI) -> float:
        rating = max(0, min(1, (poi.rating - 3) / 2))
        reviews = min(poi.review_count / 8000, 1)
        return rating * 0.6 + poi.popularity * 0.25 + reviews * 0.15

    def _queue_score(self, poi: POI) -> float:
        return max(0, 1 - min(poi.queue_minutes, 90) / 100 - max(poi.crowd_level, poi.live_crowd_level) * 0.25)

    def _walking_score(self, poi: POI) -> float:
        return {"low": 1, "medium": 0.55, "high": 0.12}.get(poi.walking_intensity, 0.45)

    def _distance_score(self, current_lat: float | None, current_lng: float | None, poi: POI) -> float:
        distance = self._distance_km(current_lat, current_lng, poi)
        return 1 if distance is None else max(0, 1 - min(distance, 15) / 15)

    def _food_score(self, poi: POI, request: RoutePlanRequest) -> float:
        if poi.category in {"restaurant", "cafe", "market"}:
            return 1
        if poi.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}:
            return 1
        return poi.food_nearby * 0.4

    def _photo_citywalk_score(self, poi: POI) -> float:
        tags = set(poi.tags + poi.highlight_text_tags)
        tag_hit = bool(tags & {"拍照", "夜景", "经典", "小众", "文艺", "citywalk"})
        category_hit = poi.category in {"landmark", "gallery", "night_view", "market"}
        return max(poi.photo_friendly, 0.85 if tag_hit or category_hit else 0)

    def _photo_food_score(self, poi: POI) -> float:
        if not self._is_food_poi_obj(poi):
            return 0
        text = " ".join([poi.name, poi.highlight_text, poi.ugc_tip, *poi.tags, *poi.highlight_text_tags, *poi.experience_tags])
        photo_hit = any(term in text for term in ["拍照", "出片", "好看", "环境", "文艺", "经典", "网红"])
        return max(0.55, poi.photo_friendly, 0.95 if photo_hit else 0)

    def _nature_score(self, poi: POI) -> float:
        text = " ".join([poi.name, poi.category, poi.primary_category, poi.highlight_text, *poi.tags, *poi.highlight_text_tags, *poi.experience_tags])
        if poi.category == "park" or poi.primary_category == "nature":
            return 1
        return 0.9 if any(term in text for term in ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林"]) else 0

    def _time_fit_score(self, poi: POI, request: RoutePlanRequest) -> float:
        minutes = self._parse_time(request.intent.start_time)
        score = 0.35
        if self._minutes_in_range(minutes, self._parse_time(poi.open_time), self._parse_time(poi.close_time)):
            score += 0.25
        if self._before_last_entry(minutes, poi):
            score += 0.2
        if self._time_slot(minutes) in poi.suitable_time_slots:
            score += 0.2
        return min(score + poi.night_activity * 0.15 if self._time_slot(minutes) in {"evening", "night"} else score, 1)

    def _nearby_bonus(self, selected_ids: set[str], poi: POI, pois: list[POI]) -> float:
        selected = [candidate for candidate in pois if candidate.id in selected_ids]
        if any(poi.id in candidate.nearby_poi_ids or candidate.id in poi.nearby_poi_ids for candidate in selected):
            return 0.3
        return 0

    def _diversity_penalty(self, selected_ids: set[str], poi: POI, pois: list[POI], objective: str, request: RoutePlanRequest) -> float:
        selected = [candidate for candidate in pois if candidate.id in selected_ids]
        if not selected:
            return 0

        counts = self._composition(selected)
        penalty = 0.0
        allows_coffee_repeat = self._allows_repeated_coffee(request)
        allows_meal_repeat = self._allows_repeated_meals(request)

        if "coffee_break" in poi.route_roles and counts["coffee"] >= 1 and not allows_coffee_repeat:
            penalty += 1.1
        if "meal" in poi.route_roles and counts["meal"] >= 1 and not allows_meal_repeat:
            penalty += 0.85

        if selected[-1].primary_category and selected[-1].primary_category == poi.primary_category:
            penalty += 0.45
        if set(selected[-1].route_roles) & set(poi.route_roles):
            penalty += 0.25

        primary_count = counts["primary_categories"].get(poi.primary_category, 0)
        if primary_count >= 2:
            penalty += 0.35 * primary_count

        if objective == "photo_citywalk" and poi.primary_category in {"food", "cafe"} and counts["main_activity"] == 0:
            penalty += 0.8
        if objective == "indoor_rainy" and poi.primary_category in {"food", "cafe"} and counts["indoor_main"] == 0:
            penalty += 0.7

        return penalty

    def _missing_role_bonus(self, selected_ids: set[str], poi: POI, pois: list[POI], objective: str, request: RoutePlanRequest) -> float:
        selected = [candidate for candidate in pois if candidate.id in selected_ids]
        counts = self._composition(selected)
        bonus = 0.0

        if counts["main_activity"] == 0 and "main_activity" in poi.route_roles:
            bonus += 0.65
        if objective == "balanced":
            if counts["meal"] == 0 and "meal" in poi.route_roles:
                bonus += 0.28
            if counts["photo"] == 0 and "photo_stop" in poi.route_roles:
                bonus += 0.22
            if counts["rest"] == 0 and ("rest_stop" in poi.route_roles or "coffee_break" in poi.route_roles):
                bonus += 0.18
        elif objective == "budget":
            if "main_activity" in poi.route_roles and poi.avg_price <= request.intent.budget_per_person * 0.35:
                bonus += 0.35
            if counts["meal"] == 0 and ("meal" in poi.route_roles or "snack" in poi.route_roles):
                bonus += 0.18
        elif objective == "food_first":
            if counts["main_activity"] == 0 and ("main_activity" in poi.route_roles or "photo_stop" in poi.route_roles):
                bonus += 0.35
            if counts["meal"] == 0 and "meal" in poi.route_roles:
                bonus += 0.45
            if counts["coffee"] == 0 and "coffee_break" in poi.route_roles:
                bonus += 0.2
        elif objective == "photo_food":
            if counts["meal"] == 0 and self._is_food_poi_obj(poi):
                bonus += 0.55
            if counts["photo"] == 0 and ("photo_stop" in poi.route_roles or self._photo_food_score(poi) >= 0.8):
                bonus += 0.45
        elif objective == "nature_relax":
            if counts["main_activity"] == 0 and self._nature_score(poi) > 0:
                bonus += 0.6
            if counts["rest"] == 0 and ("rest_stop" in poi.route_roles or poi.walking_intensity == "low"):
                bonus += 0.18
        elif objective == "photo_citywalk":
            if counts["photo"] == 0 and "photo_stop" in poi.route_roles:
                bonus += 0.55
            if counts["main_activity"] == 0 and "main_activity" in poi.route_roles:
                bonus += 0.35
        elif objective == "indoor_rainy":
            if poi.indoor and "main_activity" in poi.route_roles:
                bonus += 0.55 if counts["indoor_main"] == 0 else 0.25
            if counts["rest"] == 0 and poi.indoor and ("rest_stop" in poi.route_roles or "meal" in poi.route_roles):
                bonus += 0.15
        elif objective == "low_walking":
            if "transit_anchor" in poi.route_roles:
                bonus += 0.25
            if counts["main_activity"] == 0 and "main_activity" in poi.route_roles:
                bonus += 0.35
            if counts["rest"] == 0 and ("rest_stop" in poi.route_roles or "meal" in poi.route_roles):
                bonus += 0.15

        return bonus

    def _composition(self, pois: list[POI]) -> dict:
        primary_counts: dict[str, int] = {}
        role_counts: dict[str, int] = {}
        for poi in pois:
            primary_counts[poi.primary_category] = primary_counts.get(poi.primary_category, 0) + 1
            for role in poi.route_roles:
                role_counts[role] = role_counts.get(role, 0) + 1
        return {
            "coffee": role_counts.get("coffee_break", 0),
            "meal": role_counts.get("meal", 0),
            "main_activity": role_counts.get("main_activity", 0),
            "photo": role_counts.get("photo_stop", 0),
            "rest": role_counts.get("rest_stop", 0),
            "indoor_main": sum(1 for poi in pois if poi.indoor and "main_activity" in poi.route_roles),
            "primary_categories": primary_counts,
            "route_roles": role_counts,
        }

    def _allows_repeated_coffee(self, request: RoutePlanRequest) -> bool:
        terms = request.intent.preferences + request.user_profile.tags + request.user_profile.preferences
        return self._has_any(set(terms), ["咖啡探店", "咖啡路线", "多家咖啡", "咖啡馆"])

    def _allows_repeated_meals(self, request: RoutePlanRequest) -> bool:
        terms = request.intent.preferences + request.user_profile.tags + request.user_profile.preferences
        return self._has_any(set(terms), ["美食路线", "扫街", "吃很多家", "小吃街", "多家餐厅"])

    def _food_replacement(
        self,
        pois: list[POI],
        selected_ids: set[str],
        objective: str,
        request: RoutePlanRequest,
        state: RouteBuildState,
        time_limit: int,
    ) -> POI | None:
        food_candidates = [poi for poi in pois if poi.id not in selected_ids and self._is_food_poi_obj(poi)]
        viable = [
            poi
            for poi in food_candidates
            if state.elapsed_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes
            <= time_limit
        ]
        if not viable:
            return None
        return max(viable, key=lambda poi: self._poi_score(poi, objective, request, state.current_lat, state.current_lng))

    def _route_wants_food(self, objective: str, request: RoutePlanRequest) -> bool:
        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        return objective in {"food_first", "photo_food"} or self._has_any(terms, ["吃好", "咖啡", "聚餐", "餐厅", "美食"])

    def _is_food_poi(self, stop: RouteStop) -> bool:
        return stop.category in {"restaurant", "cafe", "market"} or stop.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}

    def _is_food_poi_obj(self, poi: POI) -> bool:
        return poi.category in {"restaurant", "cafe", "market"} or poi.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}

    def _is_food_poi_id(self, poi_id: str, pois: list[POI]) -> bool:
        poi = next((candidate for candidate in pois if candidate.id == poi_id), None)
        return bool(poi and self._is_food_poi_obj(poi))

    def _leg_minutes(self, current_lat: float | None, current_lng: float | None, poi: POI) -> int:
        return self._travel_minutes(self._distance_km(current_lat, current_lng, poi))

    def _distance_penalty(self, current_lat: float | None, current_lng: float | None, poi: POI) -> float:
        distance = self._distance_km(current_lat, current_lng, poi)
        return 0 if distance is None else min(distance, 12) * 0.04

    def _distance_km(self, current_lat: float | None, current_lng: float | None, poi: POI) -> float | None:
        if current_lat is None or current_lng is None:
            return None
        radius_km = 6371
        dlat = math.radians(poi.lat - current_lat)
        dlng = math.radians(poi.lng - current_lng)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(current_lat)) * math.cos(math.radians(poi.lat)) * math.sin(dlng / 2) ** 2
        )
        return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _travel_minutes(self, distance_km: float | None) -> int:
        if distance_km is None:
            return 0
        if distance_km <= 1:
            return max(5, round(distance_km * 12))
        if distance_km <= 5:
            return round(8 + distance_km * 5)
        return round(12 + distance_km * 4)

    def _transport_mode(self, distance_km: float | None, poi: POI) -> str | None:
        if distance_km is None:
            return None
        if distance_km <= 1:
            return "walk"
        if poi.recommended_transport:
            return "/".join(poi.recommended_transport[:2])
        if distance_km <= 5:
            return "metro/taxi"
        return "taxi/metro"

    def _parse_time(self, value: str) -> int:
        match = re.search(r"(\d{1,2}):?(\d{2})?", value)
        if not match:
            return 14 * 60
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        return hour * 60 + minute

    def _format_time(self, minutes: int) -> str:
        minutes = minutes % (24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _time_slot(self, minutes: int) -> str:
        hour = minutes // 60
        if 5 <= hour < 11:
            return "morning"
        if 11 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 21:
            return "evening"
        return "night"

    def _minutes_in_range(self, minutes: int, start: int, end: int) -> bool:
        if end >= start:
            return start <= minutes <= end
        return minutes >= start or minutes <= end

    def _before_last_entry(self, minutes: int, poi: POI) -> bool:
        open_minutes = self._parse_time(poi.open_time)
        close_minutes = self._parse_time(poi.close_time)
        last_entry_minutes = self._parse_time(poi.last_entry_time)
        check_minutes = minutes
        if close_minutes < open_minutes and minutes < open_minutes:
            check_minutes += 24 * 60
        if close_minutes < open_minutes and last_entry_minutes < open_minutes:
            last_entry_minutes += 24 * 60
        return check_minutes <= last_entry_minutes

    def _route_elapsed_minutes(self, start_time: str, stops: list[RouteStop]) -> int:
        if not stops:
            return 0
        start = self._parse_time(start_time)
        end = self._parse_time(stops[-1].end_time)
        if end < start:
            end += 24 * 60
        return end - start

    def _stop_reason(self, poi: POI, objective: str, request: RoutePlanRequest, start_minutes: int) -> str:
        if objective == "budget":
            return f"人均约 {poi.avg_price} 元，适合控制预算"
        if objective == "low_walking":
            return f"步行强度 {poi.walking_intensity}，便于轻松衔接"
        if objective == "food_first" and self._is_food_poi_obj(poi):
            return f"{poi.meal_type} 节点，匹配餐饮和休息需求"
        if objective == "photo_food":
            return "餐饮和拍照环境匹配本轮强偏好"
        if objective == "nature_relax":
            return "自然风景或低强度休闲体验较强"
        if objective == "photo_citywalk":
            return "拍照、街区或 citywalk 体验较强"
        if objective == "indoor_rainy":
            return "室内或雨天友好，天气风险较低"
        if objective == "night_friendly":
            return "晚间适配度高，适合作为夜间节点"
        if self._time_slot(start_minutes) in poi.suitable_time_slots:
            return "到达时间匹配推荐游玩时段"
        return "符合当前候选路线结构"

    def _summary(
        self,
        objective: str,
        stop_count: int,
        total_cost: int,
        total_queue: int,
        total_travel: int,
        score: int,
        breakdown: RouteScoreBreakdown,
    ) -> str:
        objective_text = {
            "balanced": "综合平衡推荐",
            "budget": "省钱推荐",
            "low_walking": "少走路推荐",
            "food_first": "餐饮优先推荐",
            "photo_food": "拍照餐饮推荐",
            "nature_relax": "自然风景推荐",
            "photo_citywalk": "拍照 citywalk 推荐",
            "indoor_rainy": "室内雨天推荐",
            "night_friendly": "夜间友好推荐",
        }[objective]
        score_text = f"综合评分 {score} 分，" if score else ""
        advantage = self._summary_advantage(objective, total_cost, total_queue, total_travel, breakdown)
        return f"{objective_text}，{score_text}包含 {stop_count} 个点，人均约 {total_cost} 元，排队 {total_queue} 分钟，路上约 {total_travel} 分钟，优势是{advantage}。"

    def _summary_advantage(
        self,
        objective: str,
        total_cost: int,
        total_queue: int,
        total_travel: int,
        breakdown: RouteScoreBreakdown,
    ) -> str:
        objective_advantages = {
            "budget": f"人均约 {total_cost} 元，预算压力相对更低",
            "low_walking": f"路上约 {total_travel} 分钟，点位衔接更轻松",
            "food_first": "餐饮和休息节点更突出，适合把吃好放在优先级前面",
            "photo_food": "餐饮和拍照环境匹配度更高",
            "nature_relax": "自然风景和轻松休闲体验更突出",
            "photo_citywalk": "拍照、街区和漫步体验更集中",
            "indoor_rainy": "室内点位和雨天友好度更高",
            "night_friendly": "晚间可玩性和夜景体验更强",
        }
        if objective in objective_advantages:
            return objective_advantages[objective]
        strongest_dimension = max(
            [
                ("质量、排队、预算和距离比较均衡", breakdown.quality),
                ("排队压力较低", breakdown.queue),
                ("预算更可控", breakdown.budget),
                ("点位衔接更顺", breakdown.distance),
                ("更贴合用户偏好", breakdown.preference),
            ],
            key=lambda item: item[1],
        )
        return strongest_dimension[0]

    def _reasons(
        self,
        objective: str,
        stops: list[RouteStop],
        total_cost: int,
        total_queue: int,
        total_distance: float,
        breakdown: RouteScoreBreakdown,
    ) -> list[str]:
        reasons = [self.OBJECTIVE_TITLES[objective].replace("候选路线", "胜出")]
        strongest_dimension = max(
            [
                ("质量表现最好", breakdown.quality),
                ("排队控制最好", breakdown.queue),
                ("预算匹配最好", breakdown.budget),
                ("距离衔接最好", breakdown.distance),
                ("偏好匹配最好", breakdown.preference),
            ],
            key=lambda item: item[1],
        )
        if strongest_dimension[1] > 0:
            reasons.append(strongest_dimension[0])
        if any(self._is_food_poi(stop) for stop in stops):
            reasons.append("包含餐饮或休息节点")
        if any(stop.indoor for stop in stops):
            reasons.append("包含室内点位")
        if total_queue <= 30:
            reasons.append("排队压力较低")
        if total_cost <= 300:
            reasons.append("预算可控")
        if total_distance <= 8:
            reasons.append("点位相对集中")
        return reasons[:4]

    def _has_any(self, terms: set[str], values: list[str]) -> bool:
        return any(value in term or term in value for term in terms for value in values)

    def _objective_data_counts(self, pois: list[POI]) -> dict[str, int]:
        return {
            "photo_food": sum(1 for poi in pois if self._photo_food_score(poi) > 0),
            "food_first": sum(1 for poi in pois if self._is_food_poi_obj(poi)),
            "nature_relax": sum(1 for poi in pois if self._nature_score(poi) > 0),
            "photo_citywalk": sum(1 for poi in pois if self._photo_citywalk_score(poi) > 0),
            "indoor_rainy": sum(1 for poi in pois if poi.indoor or poi.rainy_day_score >= 0.7),
            "night_friendly": sum(1 for poi in pois if poi.night_activity >= 0.7 or {"evening", "night"} & set(poi.suitable_time_slots)),
            "low_walking": sum(1 for poi in pois if poi.walking_intensity == "low"),
            "budget": sum(1 for poi in pois if poi.avg_price <= 80 or poi.budget_friendly >= 0.8),
            "balanced": len(pois),
        }
