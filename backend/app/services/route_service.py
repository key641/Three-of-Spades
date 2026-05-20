import math
import re

from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RoutePlanResponse, RouteStop
from app.services.scoring_service import ScoringService


class RouteService:
    """B-owned module: creates route candidates and score breakdowns."""

    OBJECTIVE_TITLES = {
        "balanced": "综合最优路线",
        "low_queue": "少排队轻松路线",
        "budget": "更省钱路线",
        "low_walking": "少走路路线",
        "food_first": "吃好优先路线",
        "photo_citywalk": "拍照 Citywalk 路线",
        "indoor_rainy": "室内雨天路线",
    }

    def __init__(self) -> None:
        self.scoring_service = ScoringService()

    def generate_routes(self, request: RoutePlanRequest) -> RoutePlanResponse:
        pois = request.candidate_pois
        if not pois:
            return RoutePlanResponse(routes=[])

        objectives = self._select_objectives(request)
        routes = [self._build_route(pois, objective, request) for objective in objectives]
        return RoutePlanResponse(routes=[route for route in routes if route.stops])

    def _select_objectives(self, request: RoutePlanRequest) -> list[str]:
        if not request.intent.preferences:
            return ["balanced", "low_queue", "budget"]

        terms = set(request.intent.preferences + request.intent.avoid_tags)
        weighted_candidates = [
            ("low_queue", request.strategy_weights.queue, self._has_any(terms, ["少排队", "别排队", "不排队"])),
            ("budget", request.strategy_weights.budget, self._has_any(terms, ["更省钱", "省钱", "便宜"])),
            ("low_walking", request.strategy_weights.distance, self._has_any(terms, ["少走路", "轻松"])),
            ("food_first", request.strategy_weights.preference, self._has_any(terms, ["吃好", "聚餐", "餐厅", "美食"])),
            ("photo_citywalk", request.strategy_weights.preference, self._has_any(terms, ["拍照", "citywalk", "散步"])),
            ("indoor_rainy", request.strategy_weights.preference, self._has_any(terms, ["室内", "雨天", "下雨"])),
        ]
        selected = ["balanced"]
        for objective, _weight, matched in weighted_candidates:
            if matched and objective not in selected:
                selected.append(objective)
        for objective, _weight, _matched in sorted(weighted_candidates, key=lambda item: item[1], reverse=True):
            if len(selected) >= 3:
                break
            if objective not in selected:
                selected.append(objective)
        for objective in ["low_queue", "budget"]:
            if len(selected) >= 3:
                break
            if objective not in selected:
                selected.append(objective)
        return selected[:3]

    def _build_route(self, pois: list[POI], objective: str, request: RoutePlanRequest) -> Route:
        remaining = sorted(pois, key=lambda poi: self._poi_score(poi, objective, request), reverse=True)
        time_limit = max(60, request.intent.duration_hours * 60)
        current_minutes = self._parse_time(request.intent.start_time)
        elapsed = 0
        current_lat = request.intent.start_lat
        current_lng = request.intent.start_lng
        stops: list[RouteStop] = []
        selected_ids: set[str] = set()

        must_include_food = self._intent_wants_food(request) or objective == "food_first"
        if must_include_food:
            food = self._best_fit(
                [poi for poi in remaining if poi.category in {"restaurant", "cafe", "market"}],
                objective,
                request,
                current_lat,
                current_lng,
                time_limit,
                elapsed,
            )
            if food is not None:
                stop, current_minutes, elapsed, current_lat, current_lng = self._append_stop(
                    food,
                    current_minutes,
                    elapsed,
                    current_lat,
                    current_lng,
                    request,
                    objective,
                )
                stops.append(stop)
                selected_ids.add(food.id)

        while len(stops) < 5:
            target = self._best_fit(
                [poi for poi in remaining if poi.id not in selected_ids],
                objective,
                request,
                current_lat,
                current_lng,
                time_limit,
                elapsed,
            )
            if target is None:
                break
            stop, current_minutes, elapsed, current_lat, current_lng = self._append_stop(
                target,
                current_minutes,
                elapsed,
                current_lat,
                current_lng,
                request,
                objective,
            )
            stops.append(stop)
            selected_ids.add(target.id)
            if len(stops) >= 3 and elapsed >= time_limit * 0.72:
                break

        if len(stops) < 3:
            stops = self._fill_short_route(
                stops,
                remaining,
                selected_ids,
                current_minutes,
                elapsed,
                time_limit,
                request,
                objective,
            )

        score_breakdown = self.scoring_service.score(
            stops,
            objective,
            budget_per_person=request.intent.budget_per_person,
            strategy_weights=request.strategy_weights,
        )
        total_travel = sum(stop.travel_minutes_from_previous or 0 for stop in stops)
        total_distance = round(sum(stop.distance_km_from_previous or 0 for stop in stops), 1)
        total_queue = sum(stop.queue_minutes for stop in stops)
        total_cost = sum(stop.estimated_cost for stop in stops)
        return Route(
            route_id=f"route_{objective}",
            title=self.OBJECTIVE_TITLES[objective],
            objective=objective,
            summary=self._summary(objective, total_cost, total_queue, total_travel),
            total_duration_minutes=self._route_elapsed_minutes(request.intent.start_time, stops),
            total_cost_per_person=total_cost,
            total_queue_minutes=total_queue,
            total_travel_minutes=total_travel,
            total_distance_km=total_distance,
            score=self.scoring_service.overall_score(score_breakdown, request.strategy_weights, objective),
            score_breakdown=score_breakdown,
            stops=stops,
            reasons=self._reasons(objective, stops, total_cost, total_queue, total_distance),
        )

    def _best_fit(
        self,
        candidates: list[POI],
        objective: str,
        request: RoutePlanRequest,
        current_lat: float | None,
        current_lng: float | None,
        time_limit: int,
        elapsed: int,
    ) -> POI | None:
        viable = [
            poi
            for poi in candidates
            if elapsed + self._leg_minutes(current_lat, current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes
            <= time_limit
        ]
        if not viable:
            return None
        return max(
            viable,
            key=lambda poi: self._poi_score(poi, objective, request) - self._distance_penalty(current_lat, current_lng, poi),
        )

    def _append_stop(
        self,
        poi: POI,
        current_minutes: int,
        elapsed: int,
        current_lat: float | None,
        current_lng: float | None,
        request: RoutePlanRequest,
        objective: str,
    ) -> tuple[RouteStop, int, int, float, float]:
        distance = self._distance_km(current_lat, current_lng, poi)
        travel_minutes = self._travel_minutes(distance)
        transport_mode = self._transport_mode(distance)
        start_minutes = current_minutes + travel_minutes
        end_minutes = start_minutes + poi.queue_minutes + poi.visit_duration_minutes
        stop = RouteStop(
            poi_id=poi.id,
            name=poi.name,
            category=poi.category,
            start_time=self._format_time(start_minutes),
            end_time=self._format_time(end_minutes),
            estimated_cost=poi.avg_price,
            queue_minutes=poi.queue_minutes,
            tags=poi.tags,
            travel_minutes_from_previous=travel_minutes if distance is not None else None,
            distance_km_from_previous=round(distance, 1) if distance is not None else None,
            transport_mode_from_previous=transport_mode,
            reason=self._stop_reason(poi, objective, request),
        )
        elapsed += travel_minutes + poi.queue_minutes + poi.visit_duration_minutes
        return stop, end_minutes, elapsed, poi.lat, poi.lng

    def _fill_short_route(
        self,
        stops: list[RouteStop],
        remaining: list[POI],
        selected_ids: set[str],
        current_minutes: int,
        elapsed: int,
        time_limit: int,
        request: RoutePlanRequest,
        objective: str,
    ) -> list[RouteStop]:
        current_lat = None
        current_lng = None
        if stops:
            last = next((poi for poi in remaining if poi.id == stops[-1].poi_id), None)
            if last is not None:
                current_lat, current_lng = last.lat, last.lng
        for poi in remaining:
            if len(stops) >= 3:
                break
            if poi.id in selected_ids:
                continue
            if elapsed + self._leg_minutes(current_lat, current_lng, poi) + poi.queue_minutes + poi.visit_duration_minutes > time_limit:
                continue
            stop, current_minutes, elapsed, current_lat, current_lng = self._append_stop(
                poi,
                current_minutes,
                elapsed,
                current_lat,
                current_lng,
                request,
                objective,
            )
            stops.append(stop)
            selected_ids.add(poi.id)
        return stops

    def _poi_score(self, poi: POI, objective: str, request: RoutePlanRequest) -> float:
        quality = max(0, min(1, (poi.rating - 3) / 2))
        queue = max(0, 1 - min(poi.queue_minutes, 90) / 90)
        budget = 1 if poi.avg_price <= request.intent.budget_per_person else 0.25
        preference = self._preference_match(poi, request)
        start_distance = self._distance_km(request.intent.start_lat, request.intent.start_lng, poi)
        distance = 1 if start_distance is None else max(0, 1 - min(start_distance, 20) / 20)
        score = quality * 0.32 + queue * 0.2 + budget * 0.16 + preference * 0.2 + distance * 0.12
        if objective == "low_queue":
            score += queue * 0.45
        elif objective == "budget":
            score += budget * 0.45 - min(poi.avg_price, 300) / 1000
        elif objective == "low_walking":
            score += distance * 0.45
        elif objective == "food_first":
            score += (0.65 if poi.category in {"restaurant", "cafe", "market"} else 0)
        elif objective == "photo_citywalk":
            score += self._tag_match(poi, ["拍照", "夜景", "经典", "小众", "citywalk", "散步"]) * 0.65
        elif objective == "indoor_rainy":
            score += (0.65 if poi.indoor else 0)
        return score

    def _preference_match(self, poi: POI, request: RoutePlanRequest) -> float:
        terms = request.intent.preferences + request.user_profile.tags
        if not terms:
            return 0
        matched = sum(1 for term in terms if self._term_matches_poi(term, poi))
        return matched / len(terms)

    def _tag_match(self, poi: POI, terms: list[str]) -> float:
        return sum(1 for term in terms if self._term_matches_poi(term, poi)) / len(terms)

    def _term_matches_poi(self, term: str, poi: POI) -> bool:
        text = " ".join([poi.name, poi.category, *poi.tags]).lower()
        aliases = {
            "少排队": ["少排队", "不排队"],
            "吃好": ["餐厅", "美食", "聚餐", "菜", "restaurant"],
            "citywalk": ["citywalk", "街区", "散步", "landmark", "拍照"],
            "拍照": ["拍照", "夜景", "经典"],
            "室内": ["室内", "museum", "gallery", "theater", "shopping", "cafe"],
            "雨天": ["室内", "museum", "gallery", "theater", "shopping", "cafe"],
        }
        return any(value.lower() in text for value in aliases.get(term, [term]))

    def _leg_minutes(self, current_lat: float | None, current_lng: float | None, poi: POI) -> int:
        return self._travel_minutes(self._distance_km(current_lat, current_lng, poi))

    def _distance_penalty(self, current_lat: float | None, current_lng: float | None, poi: POI) -> float:
        distance = self._distance_km(current_lat, current_lng, poi)
        return 0 if distance is None else min(distance, 12) * 0.035

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

    def _transport_mode(self, distance_km: float | None) -> str | None:
        if distance_km is None:
            return None
        if distance_km <= 1:
            return "walk"
        if distance_km <= 5:
            return "metro/taxi"
        return "taxi/metro"

    def _wants_food(self, request: RoutePlanRequest) -> bool:
        return self._has_any(set(request.intent.preferences + request.user_profile.tags), ["吃好", "聚餐", "餐厅", "美食"])

    def _intent_wants_food(self, request: RoutePlanRequest) -> bool:
        return self._has_any(set(request.intent.preferences), ["吃好", "聚餐", "餐厅", "美食"])

    def _has_any(self, terms: set[str], values: list[str]) -> bool:
        return any(value in term or term in value for term in terms for value in values)

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

    def _route_elapsed_minutes(self, start_time: str, stops: list[RouteStop]) -> int:
        if not stops:
            return 0
        start = self._parse_time(start_time)
        end = self._parse_time(stops[-1].end_time)
        if end < start:
            end += 24 * 60
        return end - start

    def _stop_reason(self, poi: POI, objective: str, request: RoutePlanRequest) -> str:
        if objective == "low_queue":
            return f"预计排队 {poi.queue_minutes} 分钟，节奏更轻松"
        if objective == "budget":
            return f"人均约 {poi.avg_price} 元，预算压力低"
        if objective == "low_walking":
            return "点位衔接紧凑，减少来回折返"
        if objective == "food_first" and poi.category in {"restaurant", "cafe", "market"}:
            return "优先满足吃好和休息需求"
        if objective == "photo_citywalk":
            return "适合拍照和 citywalk 体验"
        if objective == "indoor_rainy":
            return "室内或雨天友好，受天气影响小"
        if self._term_matches_poi("吃好", poi) and self._wants_food(request):
            return "匹配餐饮偏好"
        return "匹配当前路线目标"

    def _summary(self, objective: str, total_cost: int, total_queue: int, total_travel: int) -> str:
        objective_text = {
            "balanced": "综合平衡评分、预算、排队和距离",
            "low_queue": "优先压低排队时间",
            "budget": "优先控制人均花费",
            "low_walking": "优先减少交通和步行折返",
            "food_first": "优先安排餐饮和休息节点",
            "photo_citywalk": "优先串联拍照和 citywalk 点位",
            "indoor_rainy": "优先选择室内和雨天友好点位",
        }[objective]
        return f"{objective_text}，预计人均 {total_cost} 元，排队 {total_queue} 分钟，路上约 {total_travel} 分钟。"

    def _reasons(self, objective: str, stops: list[RouteStop], total_cost: int, total_queue: int, total_distance: float) -> list[str]:
        reasons = [self.OBJECTIVE_TITLES[objective].replace("路线", "")]
        if total_queue <= 30:
            reasons.append("排队总时长较低")
        if total_cost <= 300:
            reasons.append("预算可控")
        if total_distance <= 8:
            reasons.append("点位集中，少绕路")
        if any(stop.category in {"restaurant", "cafe", "market"} for stop in stops):
            reasons.append("包含餐饮休息节点")
        return reasons[:4]
