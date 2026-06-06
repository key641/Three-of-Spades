import math
import re
from dataclasses import dataclass
from collections.abc import Callable

from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RoutePlanResponse, RouteScoreBreakdown, RouteStop
from app.services.amap_service import AmapService, GeoPoint, RouteLeg
from app.services.route_rerank_service import RouteRerankService
from app.services.scoring_service import ScoringService
from app.services.strategy_service import StrategyService


@dataclass(frozen=True)
class RouteBuildState:
    current_minutes: int
    elapsed_minutes: int
    current_lat: float | None
    current_lng: float | None


@dataclass(frozen=True)
class RouteBeamState:
    stops: tuple[RouteStop, ...]
    selected_ids: frozenset[str]
    state: RouteBuildState
    score: float


class RouteService:
    """B-owned module: creates route candidates before final scoring."""

    # 各城市中心坐标 (latitude, longitude)
    CITY_CENTERS = {
        "上海": (31.2304, 121.4737),
        "北京": (39.9042, 116.4074),
        "广州": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579),
        "成都": (30.5728, 104.0668),
        "杭州": (30.2741, 120.1551),
        "南京": (32.0603, 118.7969),
        "武汉": (30.5928, 114.3055),
        "西安": (34.3416, 108.9398),
        "苏州": (31.2989, 120.5954),
        "重庆": (29.4316, 106.9123),
    }

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

    INTERNAL_CANDIDATES_PER_OBJECTIVE = 10
    START_SEEDS_PER_OBJECTIVE = 12
    BEAM_WIDTH = 6
    BRANCH_FACTOR = 8
    CANDIDATES_PER_OBJECTIVE = INTERNAL_CANDIDATES_PER_OBJECTIVE

    def __init__(self, amap_service: AmapService | None = None) -> None:
        self.amap_service = amap_service or AmapService()
        self.scoring_service = ScoringService()
        self.rerank_service = RouteRerankService()
        self.strategy_service = StrategyService()

    def generate_routes(self, request: RoutePlanRequest, on_route: Callable[[Route], None] | None = None) -> RoutePlanResponse:
        if not request.candidate_pois:
            return RoutePlanResponse(routes=[])

        # Demo only has reliable map/POI coverage for Shanghai and Beijing.
        # Other cities may use cloned fallback POIs, so assigning real city centers
        # can make every candidate too far away to fit the time window.
        if request.intent.start_lat is None or request.intent.start_lng is None:
            city = request.intent.city
            if city in {"上海", "北京"} and city in self.CITY_CENTERS:
                lat, lng = self.CITY_CENTERS[city]
                request.intent.start_lat = lat
                request.intent.start_lng = lng
                if not request.intent.start_location_name:
                    request.intent.start_location_name = f"({city}中心)"

        objectives = self._select_objectives(request)
        return self.generate_routes_for_objectives(request, objectives, on_route=on_route)

    def generate_routes_for_objectives(
        self,
        request: RoutePlanRequest,
        objectives: list[str],
        max_stops: int | None = None,
        routes_per_objective: int = 1,
        on_route: Callable[[Route], None] | None = None,
    ) -> RoutePlanResponse:
        if not request.candidate_pois:
            return RoutePlanResponse(routes=[])

        scored_routes: list[Route] = []
        poi_by_id = {poi.id: poi for poi in request.candidate_pois}
        valid_objectives = [objective for objective in self._unique_objectives(objectives) if objective in self.OBJECTIVE_TITLES]

        for objective in valid_objectives:
            candidates = self._build_candidates_for_objective(request.candidate_pois, objective, request, max_stops_override=max_stops)
            scored_candidates = self._score_candidates(candidates, objective, request, poi_by_id)
            scored_routes.extend(scored_candidates)

        reranked = self.rerank_service.rerank(
            scored_routes,
            request,
            poi_by_id,
            max_routes=max(1, routes_per_objective) * max(len(valid_objectives), 1),
            max_per_objective=max(1, routes_per_objective),
        )
        routes: list[Route] = []
        objective_counts: dict[str, int] = {}
        for item in reranked:
            index = objective_counts.get(item.route.objective, 0)
            objective_counts[item.route.objective] = index + 1
            finalized = self._finalize_route(item.route, item.route.objective, index)
            finalized.score = item.score
            finalized.reasons = list(dict.fromkeys([*item.reasons, *finalized.reasons]))[:4]
            finalized.summary = self._summary(
                finalized.objective,
                len(finalized.stops),
                finalized.total_cost_per_person,
                finalized.total_queue_minutes,
                finalized.total_travel_minutes,
                finalized.score,
                finalized.score_breakdown,
            )
            routes.append(finalized)
            if on_route is not None:
                on_route(finalized)

        return RoutePlanResponse(routes=routes)

    def _finalize_route(self, route: Route, objective: str, index: int = 0) -> Route:
        route.route_id = f"route_{objective}_best" if index == 0 else f"route_{objective}_candidate_{index + 1}"
        route.title = self.OBJECTIVE_TITLES[objective].replace("候选路线", "推荐路线")
        route.summary = self._summary(
            objective,
            len(route.stops),
            route.total_cost_per_person,
            route.total_queue_minutes,
            route.total_travel_minutes,
            route.score,
            route.score_breakdown,
        )
        route.reasons = self._reasons(
            objective,
            route.stops,
            route.total_cost_per_person,
            route.total_queue_minutes,
            route.total_distance_km,
            route.score_breakdown,
        )
        return route

    def _unique_objectives(self, objectives: list[str]) -> list[str]:
        result: list[str] = []
        for objective in objectives:
            if objective and objective not in result:
                result.append(objective)
        return result

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

    def _build_candidates_for_objective(self, pois: list[POI], objective: str, request: RoutePlanRequest, max_stops_override: int | None = None) -> list[Route]:
        time_limit = max(60, request.intent.duration_hours * 60)
        min_stops, max_stops = self._stop_bounds(request)
        if max_stops_override is not None:
            max_stops = min(max_stops, max(1, max_stops_override))
        min_stops = min(min_stops, max_stops)
        target_count = self._internal_candidate_limit(request, pois)
        start_pool = self._diverse_start_seeds(self._start_candidates(pois, objective, request), target_count)
        routes = self._build_beam_candidates(start_pool, pois, objective, request, time_limit, min_stops, max_stops, target_count)

        if len(routes) < target_count:
            seen = {self._route_signature(route) for route in routes}
            for seed in start_pool:
                route = self._build_candidate(seed, pois, objective, request, time_limit, min_stops, max_stops)
                signature = self._route_signature(route)
                if route.stops and len(route.stops) >= min_stops and signature not in seen:
                    routes.append(route)
                    seen.add(signature)
                if len(routes) >= target_count:
                    break

        if len(routes) < max(1, min(target_count, 4)):
            seen = {self._route_signature(route) for route in routes}
            for seed in self._start_candidates(pois, objective, request):
                route = self._build_candidate(seed, pois, objective, request, time_limit, 1, max_stops)
                signature = self._route_signature(route)
                if route.stops and signature not in seen:
                    routes.append(route)
                    seen.add(signature)
                if len(routes) >= target_count:
                    break

        return self._select_route_candidates(routes, objective, request, target_count)

    def _build_beam_candidates(
        self,
        start_pool: list[POI],
        pois: list[POI],
        objective: str,
        request: RoutePlanRequest,
        time_limit: int,
        min_stops: int,
        max_stops: int,
        target_count: int,
    ) -> list[Route]:
        beams: list[RouteBeamState] = []
        completed: list[RouteBeamState] = []
        initial_state = RouteBuildState(
            current_minutes=self._parse_time(request.intent.start_time),
            elapsed_minutes=0,
            current_lat=request.intent.start_lat,
            current_lng=request.intent.start_lng,
        )
        for seed in start_pool:
            appended = self._append_if_feasible(seed, initial_state, time_limit, objective, request)
            if appended is None:
                continue
            stop, next_state = appended
            score = self._extension_score(seed, objective, request, initial_state, frozenset(), pois, must_extend=min_stops > 1)
            beams.append(RouteBeamState(stops=(stop,), selected_ids=frozenset({seed.id}), state=next_state, score=score))

        beams = sorted(beams, key=lambda beam: beam.score, reverse=True)[: self.BEAM_WIDTH]
        seen_completed: set[tuple[str, ...]] = set()
        while beams and len(completed) < target_count * 3:
            next_beams: list[RouteBeamState] = []
            for beam in beams:
                if len(beam.stops) >= min_stops:
                    signature = tuple(stop.poi_id for stop in beam.stops)
                    if signature not in seen_completed:
                        completed.append(beam)
                        seen_completed.add(signature)
                if len(beam.stops) >= max_stops or beam.state.elapsed_minutes >= time_limit * 0.92:
                    continue
                for poi in self._beam_next_candidates(pois, beam, objective, request, time_limit, min_stops):
                    appended = self._append_if_feasible(poi, beam.state, time_limit, objective, request)
                    if appended is None:
                        continue
                    stop, next_state = appended
                    score = beam.score + self._extension_score(
                        poi,
                        objective,
                        request,
                        beam.state,
                        beam.selected_ids,
                        pois,
                        must_extend=len(beam.stops) + 1 < min_stops,
                    )
                    next_beams.append(
                        RouteBeamState(
                            stops=(*beam.stops, stop),
                            selected_ids=frozenset({*beam.selected_ids, poi.id}),
                            state=next_state,
                            score=score,
                        )
                    )
            if not next_beams:
                break
            beams = sorted(next_beams, key=lambda beam: beam.score, reverse=True)[: self.BEAM_WIDTH]

        completed.extend(beam for beam in beams if len(beam.stops) >= min_stops)
        routes = [self._route_from_stops(list(beam.stops), objective, request) for beam in sorted(completed, key=lambda beam: beam.score, reverse=True)]
        return self._select_route_candidates(routes, objective, request, target_count)

    def _beam_next_candidates(
        self,
        pois: list[POI],
        beam: RouteBeamState,
        objective: str,
        request: RoutePlanRequest,
        time_limit: int,
        min_stops: int,
    ) -> list[POI]:
        selected_ids = set(beam.selected_ids)
        candidates = [
            poi
            for poi in pois
            if poi.id not in selected_ids
            and self._passes_meal_composition(selected_ids, poi, pois, request)
            and self._is_viable_next_poi(poi, beam.state, time_limit, objective, request)
        ]
        required_food = self._route_wants_food(objective, request)
        if required_food and not any(self._is_food_poi_id(poi_id, pois) for poi_id in selected_ids):
            food_candidates = self._food_candidates_for_request(candidates, objective, request)
            if food_candidates:
                candidates = food_candidates
        must_extend = len(beam.stops) + 1 < min_stops
        return sorted(
            candidates,
            key=lambda poi: self._extension_score(poi, objective, request, beam.state, beam.selected_ids, pois, must_extend),
            reverse=True,
        )[: self.BRANCH_FACTOR]

    def _extension_score(
        self,
        poi: POI,
        objective: str,
        request: RoutePlanRequest,
        state: RouteBuildState,
        selected_ids: frozenset[str],
        pois: list[POI],
        must_extend: bool,
    ) -> float:
        selected = set(selected_ids)
        return (
            self._poi_score(poi, objective, request, state.current_lat, state.current_lng)
            + self._nearby_bonus(selected, poi, pois)
            - self._distance_penalty(state.current_lat, state.current_lng, poi)
            - self._diversity_penalty(selected, poi, pois, objective, request)
            - self._common_sense_penalty(poi, objective, request, state.current_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi), selected, pois)
            + self._missing_role_bonus(selected, poi, pois, objective, request)
            + (0.12 if must_extend else 0)
        )

    def _is_viable_next_poi(self, poi: POI, state: RouteBuildState, time_limit: int, objective: str, request: RoutePlanRequest) -> bool:
        total_add = self._leg_minutes(state.current_lat, state.current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes
        start_minutes = state.current_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi)
        return (
            state.elapsed_minutes + total_add <= time_limit
            and self._minutes_in_range(start_minutes, self._parse_time(poi.open_time), self._parse_time(poi.close_time))
            and self._before_last_entry(start_minutes, poi)
            and self._is_contextually_reasonable_poi(poi, objective, request, start_minutes)
        )

    def _internal_candidate_limit(self, request: RoutePlanRequest, pois: list[POI]) -> int:
        if len(pois) < self.INTERNAL_CANDIDATES_PER_OBJECTIVE:
            return max(1, len(pois))
        if request.intent.duration_hours <= 3:
            return 6
        return self.INTERNAL_CANDIDATES_PER_OBJECTIVE

    def _diverse_start_seeds(self, ranked: list[POI], target_count: int) -> list[POI]:
        seed_limit = max(self.START_SEEDS_PER_OBJECTIVE, target_count + 2)
        selected: list[POI] = []
        deferred: list[POI] = []
        category_counts: dict[str, int] = {}
        for poi in ranked:
            if category_counts.get(poi.category, 0) < 2:
                selected.append(poi)
                category_counts[poi.category] = category_counts.get(poi.category, 0) + 1
            else:
                deferred.append(poi)
            if len(selected) >= seed_limit:
                return selected
        selected.extend(deferred[: max(0, seed_limit - len(selected))])
        return selected

    def _select_route_candidates(self, routes: list[Route], objective: str, request: RoutePlanRequest, limit: int) -> list[Route]:
        selected: list[Route] = []
        seen_signatures: set[tuple[str, ...]] = set()
        for route in sorted(routes, key=lambda item: self._route_candidate_key(item, objective, request), reverse=True):
            signature = self._route_signature(route)
            if not signature or signature in seen_signatures:
                continue
            if any(self._route_overlap(route, existing) > 0.8 for existing in selected):
                continue
            selected.append(route)
            seen_signatures.add(signature)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            for route in sorted(routes, key=lambda item: self._route_candidate_key(item, objective, request), reverse=True):
                signature = self._route_signature(route)
                if signature and signature not in seen_signatures:
                    selected.append(route)
                    seen_signatures.add(signature)
                if len(selected) >= limit:
                    break
        return selected

    def _route_candidate_key(self, route: Route, objective: str, request: RoutePlanRequest) -> tuple[float, float, float, float]:
        structure = self._route_structure_score(route, objective)
        budget_fit = -max(0, route.total_cost_per_person - request.intent.budget_per_person * max(len(route.stops), 1))
        time_fit = -abs(route.total_duration_minutes - request.intent.duration_hours * 60 * 0.82)
        return (structure, budget_fit, time_fit, -route.total_distance_km)

    def _route_structure_score(self, route: Route, objective: str) -> float:
        stops = route.stops
        if not stops:
            return -1
        score = 0.0
        if any("main_activity" in stop.route_roles for stop in stops):
            score += 1.0
        if any("meal" in stop.route_roles or "coffee_break" in stop.route_roles or "rest_stop" in stop.route_roles for stop in stops):
            score += 0.25
        if objective in {"food_first", "photo_food"} and any(self._is_food_poi(stop) for stop in stops):
            score += 0.8
        if objective == "photo_food" and any("photo_stop" in stop.route_roles for stop in stops):
            score += 0.5
        if objective == "photo_citywalk" and any("photo_stop" in stop.route_roles for stop in stops):
            score += 0.6
        if objective == "indoor_rainy" and any(stop.indoor and "main_activity" in stop.route_roles for stop in stops):
            score += 0.8
        if objective == "night_friendly" and any("night_end" in stop.route_roles or "night" in stop.tags for stop in stops):
            score += 0.6
        if objective == "low_walking" and all((stop.transport_mode_from_previous != "walk" or (stop.distance_km_from_previous or 0) <= 1) for stop in stops):
            score += 0.6
        score -= self._route_common_sense_penalty(route)
        return score

    def _route_signature(self, route: Route) -> tuple[str, ...]:
        return tuple(stop.poi_id for stop in route.stops)

    def _route_overlap(self, route_a: Route, route_b: Route) -> float:
        ids_a = {stop.poi_id for stop in route_a.stops}
        ids_b = {stop.poi_id for stop in route_b.stops}
        if not ids_a or not ids_b:
            return 0
        return len(ids_a & ids_b) / min(len(ids_a), len(ids_b))

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
        transport_mode = self._transport_mode(distance, poi, request)
        route_leg = self._best_route_leg(state.current_lat, state.current_lng, poi, request, distance)
        travel_minutes = route_leg.duration_minutes if route_leg else self._travel_minutes(distance)
        distance_km = self._distance_from_leg(route_leg, distance)
        total_add = travel_minutes + poi.queue_minutes + poi.visit_duration_minutes
        if state.elapsed_minutes + total_add > time_limit:
            return None

        start_minutes = state.current_minutes + travel_minutes
        if not self._is_contextually_reasonable_poi(poi, objective, request, start_minutes):
            return None
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
            route_steps_from_previous=[step.instruction for step in route_leg.steps] if route_leg else [],
            reason=self._stop_reason(poi, objective, request, start_minutes),
        )
        next_state = RouteBuildState(
            current_minutes=end_minutes,
            elapsed_minutes=state.elapsed_minutes + total_add,
            current_lat=poi.lat,
            current_lng=poi.lng,
        )
        return stop, next_state

    def _route_leg(self, current_lat: float | None, current_lng: float | None, poi: POI, mode: str | None, departure_time: str | None = None) -> RouteLeg | None:
        if current_lat is None or current_lng is None or mode is None:
            return None
        return self.amap_service.route_leg(
            origin=GeoPoint(lat=current_lat, lng=current_lng),
            destination=GeoPoint(lat=poi.lat, lng=poi.lng),
            mode=mode,
            departure_time=departure_time,
        )

    def _best_route_leg(
        self,
        current_lat: float | None,
        current_lng: float | None,
        poi: POI,
        request: RoutePlanRequest,
        distance_km: float | None,
    ) -> RouteLeg | None:
        if current_lat is None or current_lng is None or distance_km is None:
            return None
        modes = self._candidate_transport_modes(distance_km, poi, request)
        legs = [self._route_leg(current_lat, current_lng, poi, mode, request.intent.start_time) for mode in modes]
        available = [leg for leg in legs if leg is not None]
        if not available:
            return None
        return self._choose_public_transit_first(available, request)

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
        candidates = [
            poi
            for poi in candidates
            if self._passes_meal_composition(selected_ids, poi, pois, request)
        ]
        if required_food and not any(self._is_food_poi_id(poi_id, pois) for poi_id in selected_ids):
            food_candidates = self._food_candidates_for_request(candidates, objective, request)
            if food_candidates:
                candidates = food_candidates

        viable = [
            poi
            for poi in candidates
            if state.elapsed_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes
            <= time_limit
            and self._is_contextually_reasonable_poi(
                poi,
                objective,
                request,
                state.current_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi),
            )
        ]
        if not viable:
            return None

        return max(
            viable,
            key=lambda poi: self._poi_score(poi, objective, request, state.current_lat, state.current_lng)
            + self._nearby_bonus(selected_ids, poi, pois)
            - self._distance_penalty(state.current_lat, state.current_lng, poi)
            - self._diversity_penalty(selected_ids, poi, pois, objective, request)
            - self._common_sense_penalty(
                poi,
                objective,
                request,
                state.current_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi),
                selected_ids,
                pois,
            )
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
        score += request.poi_relevance_scores.get(poi.id, 0) * 0.45

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
        score -= self._common_sense_penalty(poi, objective, request, self._parse_time(request.intent.start_time))
        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        if self._has_any(terms, ["citywalk", "拍照", "吃好"]) and (poi.transit_hub_nearby or "metro" in poi.recommended_transport or "bus" in poi.recommended_transport):
            score += 0.12
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
        if self._time_slot(minutes) in {"evening", "night"}:
            score += poi.night_activity * 0.15
        if self._is_coffee_poi(poi) and self._is_late_night(minutes) and not self._wants_explicit_coffee(request):
            score -= 0.45
        if self._is_meal_poi(poi) and self._time_slot(minutes) == "afternoon" and not self._wants_meal(request):
            score -= 0.25
        return max(0, min(score, 1))

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
        if self._meal_group(poi) in {"coffee", "meal"} and not self._allows_mixed_meal_nodes(request):
            other_group = "meal" if self._meal_group(poi) == "coffee" else "coffee"
            if counts[other_group] >= 1:
                penalty += 2.4

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
            if "transit_anchor" in poi.route_roles:
                bonus += 0.12
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
        if self._is_late_night(self._parse_time(request.intent.start_time)):
            return False
        terms = request.intent.preferences + request.user_profile.tags + request.user_profile.preferences
        return self._has_any(set(terms), ["咖啡探店", "咖啡路线", "多家咖啡", "咖啡馆"])

    def _allows_repeated_meals(self, request: RoutePlanRequest) -> bool:
        terms = request.intent.preferences + request.user_profile.tags + request.user_profile.preferences
        return self._has_any(set(terms), ["美食路线", "扫街", "吃很多家", "小吃街", "多家餐厅"])

    def _allows_mixed_meal_nodes(self, request: RoutePlanRequest) -> bool:
        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        wants_coffee = self._has_any(terms, ["咖啡", "下午茶", "咖啡馆", "咖啡探店"])
        wants_meal = self._has_any(terms, ["吃好", "美食", "餐厅", "正餐", "火锅", "小吃"])
        return wants_coffee and wants_meal

    def _passes_meal_composition(self, selected_ids: set[str], poi: POI, pois: list[POI], request: RoutePlanRequest) -> bool:
        group = self._meal_group(poi)
        if group not in {"coffee", "meal"} or self._allows_mixed_meal_nodes(request):
            return True
        selected = [candidate for candidate in pois if candidate.id in selected_ids]
        if not selected:
            return True
        selected_groups = {self._meal_group(candidate) for candidate in selected}
        if group == "coffee" and "coffee" in selected_groups and not self._allows_repeated_coffee(request):
            return False
        if group == "meal" and "meal" in selected_groups and not self._allows_repeated_meals(request):
            return False
        if group == "coffee" and "meal" in selected_groups:
            return False
        if group == "meal" and "coffee" in selected_groups:
            return False
        return True

    def _meal_group(self, poi: POI | RouteStop) -> str:
        if "coffee_break" in poi.route_roles or poi.category == "cafe" or poi.meal_type == "cafe":
            return "coffee"
        if "meal" in poi.route_roles or poi.category == "restaurant" or poi.meal_type in {"local_food", "fine_dining"}:
            return "meal"
        if "snack" in poi.route_roles or poi.category == "market" or poi.meal_type in {"light_meal", "fast_food"}:
            return "snack"
        return "none"

    def _food_replacement(
        self,
        pois: list[POI],
        selected_ids: set[str],
        objective: str,
        request: RoutePlanRequest,
        state: RouteBuildState,
        time_limit: int,
    ) -> POI | None:
        food_candidates = self._food_candidates_for_request(
            [poi for poi in pois if poi.id not in selected_ids and self._is_food_poi_obj(poi)],
            objective,
            request,
        )
        viable = [
            poi
            for poi in food_candidates
            if state.elapsed_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes
            <= time_limit
            and self._is_contextually_reasonable_poi(
                poi,
                objective,
                request,
                state.current_minutes + self._leg_minutes(state.current_lat, state.current_lng, poi),
            )
        ]
        if not viable:
            return None
        return max(viable, key=lambda poi: self._poi_score(poi, objective, request, state.current_lat, state.current_lng))

    def _route_wants_food(self, objective: str, request: RoutePlanRequest) -> bool:
        return self._route_wants_meal(objective, request) or self._route_wants_coffee(objective, request)

    def _route_wants_meal(self, objective: str, request: RoutePlanRequest) -> bool:
        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        return objective in {"food_first", "photo_food"} or self._has_any(terms, ["吃好", "聚餐", "餐厅", "美食", "正餐", "小吃"])

    def _route_wants_coffee(self, objective: str, request: RoutePlanRequest) -> bool:
        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        return self._has_any(terms, ["咖啡", "下午茶", "咖啡馆", "咖啡探店"])

    def _food_candidates_for_request(self, pois: list[POI], objective: str, request: RoutePlanRequest) -> list[POI]:
        wants_meal = self._route_wants_meal(objective, request)
        wants_coffee = self._route_wants_coffee(objective, request)
        if wants_coffee and not wants_meal:
            return [poi for poi in pois if self._is_coffee_poi(poi)]
        if wants_meal and not wants_coffee:
            meal_candidates = [poi for poi in pois if self._is_meal_poi(poi) or self._meal_group(poi) == "snack"]
            return meal_candidates or [poi for poi in pois if self._is_food_poi_obj(poi)]
        return [poi for poi in pois if self._is_food_poi_obj(poi)]

    def _is_food_poi(self, stop: RouteStop) -> bool:
        return stop.category in {"restaurant", "cafe", "market"} or stop.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}

    def _is_food_poi_obj(self, poi: POI) -> bool:
        return poi.category in {"restaurant", "cafe", "market"} or poi.meal_type in {"local_food", "fine_dining", "cafe", "light_meal", "fast_food"}

    def _is_coffee_poi(self, poi: POI | RouteStop) -> bool:
        return "coffee_break" in poi.route_roles or poi.category == "cafe" or poi.meal_type == "cafe"

    def _is_meal_poi(self, poi: POI | RouteStop) -> bool:
        return "meal" in poi.route_roles or poi.category == "restaurant" or poi.meal_type in {"local_food", "fine_dining"}

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

    def _transport_mode(self, distance_km: float | None, poi: POI, request: RoutePlanRequest | None = None) -> str | None:
        if distance_km is None:
            return None
        if distance_km <= 0.8 and not self._prefers_less_walking(request):
            return "walk"
        if poi.recommended_transport:
            return self._normalize_transport_mode(poi.recommended_transport[0])
        if self._prefers_less_walking(request) and distance_km > 1:
            return "taxi"
        if distance_km <= 5:
            return "metro"
        return "taxi"

    def _candidate_transport_modes(self, distance_km: float, poi: POI, request: RoutePlanRequest) -> list[str]:
        late = self._is_late_night(self._parse_time(request.intent.start_time))
        if distance_km <= 0.8 and not self._prefers_less_walking(request):
            modes = ["walk", "metro", "bus", "taxi"]
        elif distance_km > 8:
            modes = ["taxi", "metro", "bus"] if late else ["metro", "bus", "taxi"]
        elif late and distance_km > 1.5:
            modes = ["taxi", "metro", "bus"]
        elif self._prefers_less_walking(request) and distance_km > 1:
            modes = ["taxi", "metro", "bus"]
        else:
            modes = ["metro", "bus", "taxi", "walk"]
        for mode in poi.recommended_transport:
            normalized = self._normalize_transport_mode(mode)
            if normalized not in modes:
                if normalized in {"metro", "bus"}:
                    modes.insert(0, normalized)
                else:
                    modes.append(normalized)
        return modes

    def _choose_public_transit_first(self, legs: list[RouteLeg], request: RoutePlanRequest) -> RouteLeg:
        taxi = next((leg for leg in legs if self._normalize_transport_mode(leg.mode) == "taxi"), None)
        public_legs = [leg for leg in legs if self._normalize_transport_mode(leg.mode) in {"metro", "bus"}]
        if public_legs:
            best_public = min(public_legs, key=lambda leg: self._transport_score(leg, request))
            if taxi is None or self._public_transit_is_convenient(best_public, taxi, request):
                return best_public
        return min(legs, key=lambda leg: self._transport_score(leg, request))

    def _public_transit_is_convenient(self, public_leg: RouteLeg, taxi_leg: RouteLeg, request: RoutePlanRequest) -> bool:
        late = self._is_late_night(self._parse_time(request.intent.start_time))
        slack_minutes = 18 if late else (25 if self._prefers_less_walking(request) else 42)
        ratio = 1.8 if late else (2.5 if self._prefers_less_walking(request) else 4.0)
        return (
            public_leg.duration_minutes <= taxi_leg.duration_minutes + slack_minutes
            or public_leg.duration_minutes <= taxi_leg.duration_minutes * ratio
        )

    def _transport_score(self, leg: RouteLeg, request: RoutePlanRequest) -> float:
        score = leg.duration_minutes
        mode = self._normalize_transport_mode(leg.mode)
        distance_km = leg.distance_meters / 1000
        if self._prefers_less_walking(request) and mode == "walk" and distance_km > 1:
            score += distance_km * 18
        if self._is_late_night(self._parse_time(request.intent.start_time)) and mode in {"metro", "bus"}:
            score += 8
        if mode == "taxi":
            score += 4 if self._is_late_night(self._parse_time(request.intent.start_time)) else 12
        if mode in {"metro", "bus"}:
            score -= 6
        return score

    def _prefers_less_walking(self, request: RoutePlanRequest | None) -> bool:
        if request is None:
            return False
        terms = set(request.intent.preferences + request.user_profile.tags + request.user_profile.preferences)
        if self._has_any(terms, ["少走路", "轻松", "室内", "亲子", "老人"]):
            return True
        return request.intent.duration_hours <= 4 and request.intent.scenario in {"family_trip"}

    def _common_sense_penalty(
        self,
        poi: POI,
        objective: str,
        request: RoutePlanRequest,
        arrival_minutes: int | None = None,
        selected_ids: set[str] | frozenset[str] | None = None,
        pois: list[POI] | None = None,
    ) -> float:
        minutes = self._parse_time(request.intent.start_time) if arrival_minutes is None else arrival_minutes
        terms = self._request_terms(request)
        penalty = 0.0

        if self._is_coffee_poi(poi) and self._is_late_night(minutes) and not self._wants_explicit_coffee(request):
            penalty += 1.7 if objective == "night_friendly" else 1.25
        elif self._is_coffee_poi(poi) and self._is_evening(minutes) and not self._wants_explicit_coffee(request):
            penalty += 0.35

        if self._is_meal_poi(poi) and self._time_slot(minutes) == "afternoon" and not self._wants_meal(request):
            penalty += 0.45
        if self._is_meal_poi(poi) and self._time_slot(minutes) == "night" and not self._wants_meal(request):
            penalty += 0.35

        if self._is_rainy_context(request):
            if not poi.indoor and poi.walking_intensity == "high":
                penalty += 0.75
            elif not poi.indoor and poi.category in {"park", "night_view"}:
                penalty += 0.35
        if self._is_hot_context(request) and not poi.indoor and poi.walking_intensity == "high":
            penalty += 0.65
        if self._is_cold_context(request) and not poi.indoor and poi.category in {"park", "night_view"}:
            penalty += 0.35

        if self._has_any(terms, ["亲子", "老人", "轻松", "少走路"]) or request.user_profile.walking_tolerance <= 0.35:
            if poi.walking_intensity == "high":
                penalty += 0.65
            if max(poi.crowd_level, poi.live_crowd_level) >= 0.75:
                penalty += 0.25

        if selected_ids and pois:
            selected = [candidate for candidate in pois if candidate.id in selected_ids]
            if selected and selected[-1].walking_intensity == "high" and poi.walking_intensity == "high":
                penalty += 0.45
            if selected and self._distance_km(selected[-1].lat, selected[-1].lng, poi):
                distance = self._distance_km(selected[-1].lat, selected[-1].lng, poi) or 0
                if distance > 8:
                    penalty += 0.35
                if distance > 12:
                    penalty += 0.35

        return penalty

    def _is_contextually_reasonable_poi(self, poi: POI, objective: str, request: RoutePlanRequest, arrival_minutes: int) -> bool:
        if self._is_coffee_poi(poi) and self._is_late_night(arrival_minutes) and not self._wants_explicit_coffee(request):
            return False
        if objective == "night_friendly" and self._is_coffee_poi(poi) and not self._wants_explicit_coffee(request):
            return False
        return True

    def _route_common_sense_penalty(self, route: Route) -> float:
        penalty = 0.0
        for stop in route.stops:
            minutes = self._parse_time(stop.start_time)
            if self._is_coffee_poi(stop) and self._is_late_night(minutes):
                penalty += 0.7
            if stop.walking_intensity == "high":
                penalty += 0.05
        for previous, current in zip(route.stops, route.stops[1:]):
            if previous.walking_intensity == "high" and current.walking_intensity == "high":
                penalty += 0.25
            if self._is_meal_poi(previous) and self._is_coffee_poi(current):
                penalty += 0.18
        return penalty

    def _wants_explicit_coffee(self, request: RoutePlanRequest) -> bool:
        return self._has_any(self._request_terms(request), ["咖啡", "下午茶", "咖啡馆", "咖啡探店", "咖啡路线"])

    def _wants_meal(self, request: RoutePlanRequest) -> bool:
        return self._has_any(self._request_terms(request), ["吃好", "美食", "餐厅", "聚餐", "正餐", "小吃", "火锅"])

    def _request_terms(self, request: RoutePlanRequest) -> set[str]:
        return set(
            [
                *request.intent.preferences,
                *request.user_profile.tags,
                *request.user_profile.preferences,
                *[tag.tag for tag in request.strategy_tags],
            ]
        )

    def _is_rainy_context(self, request: RoutePlanRequest) -> bool:
        return self._has_any(self._request_terms(request), ["雨天", "下雨", "室内", "rain", "indoor_rainy"])

    def _is_hot_context(self, request: RoutePlanRequest) -> bool:
        return self._has_any(self._request_terms(request), ["高温", "很热", "炎热", "hot", "避暑"])

    def _is_cold_context(self, request: RoutePlanRequest) -> bool:
        return self._has_any(self._request_terms(request), ["冷", "寒冷", "大风", "cold"])

    def _is_evening(self, minutes: int) -> bool:
        return 19 * 60 <= minutes < 20 * 60

    def _is_late_night(self, minutes: int) -> bool:
        hour = (minutes // 60) % 24
        return hour >= 20 or hour < 5

    def _normalize_transport_mode(self, mode: str) -> str:
        if "walk" in mode or "步行" in mode:
            return "walk"
        if "taxi" in mode or "drive" in mode or "打车" in mode or "自驾" in mode:
            return "taxi"
        if "bus" in mode or "公交" in mode:
            return "bus"
        if "metro" in mode or "地铁" in mode:
            return "metro"
        return mode

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
