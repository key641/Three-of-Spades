from app.schemas.intent import Intent
from app.schemas.map import ExternalPOICandidate, ExternalPOIStatus, GeoPoint
from app.schemas.poi import POI
from app.schemas.route import ReplanRequest, Route, RouteChange, RoutePlanRequest, RoutePlanResponse, RouteScoreBreakdown, RouteStop
from app.schemas.user import UserProfile
from app.services.map_provider import MapProvider, MockMapProvider
from app.services.poi_service import POIService
from app.services.route_service import RouteService
from app.services.scoring_service import ScoringService


class ReplanService:
    """Partial replanning after queue, traffic, map status, or preference events."""

    QUEUE_REPLACE_THRESHOLD = 45
    TRAFFIC_WARNING_MULTIPLIER = 1.4

    def __init__(
        self,
        map_provider: MapProvider | None = None,
        poi_service: POIService | None = None,
        route_service: RouteService | None = None,
    ) -> None:
        self.map_provider = map_provider or MockMapProvider()
        self.poi_service = poi_service or POIService()
        self.route_service = route_service or RouteService()
        self.scoring_service = ScoringService()

    def replan(self, request: ReplanRequest) -> RoutePlanResponse:
        if not request.current_routes:
            return RoutePlanResponse(routes=[])

        updated_routes: list[Route] = []
        for route in request.current_routes:
            if request.selected_route_id and route.route_id != request.selected_route_id:
                updated_routes.append(route)
                continue
            updated_routes.append(self._replan_route(route, request))
        return RoutePlanResponse(routes=updated_routes)

    def _replan_route(self, route: Route, request: ReplanRequest) -> Route:
        route = route.model_copy(deep=True)
        completed_ids = set(request.completed_poi_ids)
        locked_ids = set(request.locked_poi_ids)
        event_payload = {**request.event_payload, "event_type": request.event_type, "event_label": request.event_label}
        poi_by_id = {poi.id: poi for poi in self.poi_service.all_pois()}

        completed_stops = [stop for stop in route.stops if stop.poi_id in completed_ids]
        future_stops = [stop for stop in route.stops if stop.poi_id not in completed_ids]
        if not future_stops:
            route.replan_reason = "已重新评估，所有路线点都已完成，无需调整。"
            route.data_sources = self._sources(route, self.map_provider.source)
            return route

        live_warnings: list[str] = []
        changes: list[RouteChange] = []
        replacement_used = False
        unavailable_ids: set[str] = set()
        adjusted_pois: dict[str, POI] = {}

        city = self._route_city(route, poi_by_id)
        local_candidates = self.poi_service.all_pois(city=city)
        route_poi_ids = {stop.poi_id for stop in route.stops}

        replanned_future: list[POI] = []
        for stop in future_stops:
            poi = self._poi_for_stop(stop, poi_by_id)
            status = self._live_status_for_stop(stop, event_payload)
            adjusted = self._apply_live_status(poi, status)
            adjusted_pois[adjusted.id] = adjusted

            should_replace = self._should_replace(stop, adjusted, status, request)
            if stop.poi_id in locked_ids and status.status not in {"closed", "unavailable", "sold_out"}:
                should_replace = False

            if should_replace:
                unavailable_ids.add(stop.poi_id)
                replacement = self._find_replacement(
                    original=adjusted,
                    route=route,
                    selected_poi_ids=route_poi_ids | unavailable_ids,
                    completed_ids=completed_ids,
                    locked_ids=locked_ids,
                    local_candidates=local_candidates,
                    request=request,
                    event_payload=event_payload,
                    previous_stop=completed_stops[-1] if completed_stops else None,
                )
                if replacement is not None:
                    replanned_future.append(replacement)
                    route_poi_ids.add(replacement.id)
                    replacement_used = True
                    changes.append(
                        RouteChange(
                            change_type="replace",
                            from_poi_id=stop.poi_id,
                            from_name=stop.name,
                            to_poi_id=replacement.id,
                            to_name=replacement.name,
                            reason=self._replacement_reason(status, request),
                        )
                    )
                    live_warnings.append(f"{stop.name} {self._status_warning(status, adjusted)}，已换成 {replacement.name}。")
                    continue

            replanned_future.append(adjusted)
            warning = self._status_warning(status, adjusted)
            if warning:
                live_warnings.append(f"{stop.name} {warning}。")

        new_stops = completed_stops + self._rebuild_future_stops(completed_stops, replanned_future, route, request, event_payload)
        route.stops = new_stops
        self._refresh_route_metrics(route, request, poi_by_id | adjusted_pois | {poi.id: poi for poi in replanned_future})
        route.changed_stops = changes
        route.live_warnings = live_warnings + self._traffic_warnings(new_stops, event_payload)
        route.data_sources = self._sources(route, self.map_provider.source)
        route.replan_reason = self._replan_reason(request, replacement_used, route.live_warnings)
        route.summary = self._summary(route, request, replacement_used)
        return route

    def _live_status_for_stop(self, stop: RouteStop, event_payload: dict) -> ExternalPOIStatus:
        payload = dict(event_payload)
        affected_category = str(payload.get("affected_category", ""))
        has_explicit_target = payload.get("affected_poi_id") or payload.get("affected_poi_ids")
        if affected_category and not has_explicit_target:
            if affected_category in {stop.category, stop.primary_category} or affected_category in stop.tags:
                payload["affected_poi_id"] = stop.poi_id
        return self.map_provider.get_place_status(stop.poi_id, payload)

    def _apply_live_status(self, poi: POI, status: ExternalPOIStatus) -> POI:
        updated = poi.model_copy(deep=True)
        if status.queue_minutes is not None:
            updated.queue_minutes = status.queue_minutes
        if status.live_crowd_level is not None:
            updated.live_crowd_level = status.live_crowd_level
        if status.status in {"closed", "unavailable", "sold_out"}:
            updated.risk_flags = list(dict.fromkeys([*updated.risk_flags, status.status]))
            updated.avoid_reasons = list(dict.fromkeys([*updated.avoid_reasons, status.reason or "实时状态不可用"]))
        return updated

    def _should_replace(self, stop: RouteStop, poi: POI, status: ExternalPOIStatus, request: ReplanRequest) -> bool:
        if status.status in {"closed", "unavailable", "sold_out"} or not status.is_open or not status.is_accessible:
            return True
        if request.event_type == "queue_spike" and poi.queue_minutes >= self.QUEUE_REPLACE_THRESHOLD:
            return True
        if request.event_type == "user_tired" and stop.walking_intensity == "high":
            return True
        if request.event_type == "weather_change" and not stop.indoor:
            return True
        return False

    def _find_replacement(
        self,
        original: POI,
        route: Route,
        selected_poi_ids: set[str],
        completed_ids: set[str],
        locked_ids: set[str],
        local_candidates: list[POI],
        request: ReplanRequest,
        event_payload: dict,
        previous_stop: RouteStop | None,
    ) -> POI | None:
        excluded_ids = selected_poi_ids | completed_ids | locked_ids
        candidates = [poi for poi in local_candidates if poi.id not in excluded_ids]
        viable = [
            poi
            for poi in candidates
            if self._replacement_role_score(original, poi) > 0
            and self._live_status_for_poi(poi, event_payload).status not in {"closed", "unavailable", "sold_out"}
        ]
        if not viable:
            nearby = self._external_replacements(original, previous_stop, event_payload)
            viable = [self._poi_from_external(candidate, original) for candidate in nearby]
        if not viable:
            return None

        origin = self._origin_point(previous_stop, original)
        return max(
            viable,
            key=lambda poi: self._replacement_score(original, poi, origin, request, event_payload),
        )

    def _live_status_for_poi(self, poi: POI, event_payload: dict) -> ExternalPOIStatus:
        return self.map_provider.get_place_status(poi.id, event_payload)

    def _external_replacements(
        self,
        original: POI,
        previous_stop: RouteStop | None,
        event_payload: dict,
    ) -> list[ExternalPOICandidate]:
        origin = self._origin_point(previous_stop, original)
        return self.map_provider.search_nearby_pois(
            origin,
            radius_km=2.5,
            categories=[original.category, original.primary_category],
            keywords=[original.name, *original.route_roles, *original.tags],
            event_payload=event_payload,
        )

    def _poi_from_external(self, candidate: ExternalPOICandidate, original: POI) -> POI:
        category = candidate.map_category or original.category
        roles = original.route_roles or ["main_activity"]
        return POI(
            id=next(iter(candidate.external_place_ids.values()), f"external_{candidate.name}"),
            name=candidate.name,
            city=candidate.city or original.city,
            district=candidate.district or original.district,
            address=candidate.address,
            category=category,
            external_place_ids=candidate.external_place_ids,
            source_provider=candidate.source_provider,
            map_category=candidate.map_category,
            map_category_code=candidate.map_category_code,
            canonical_poi_id=original.canonical_poi_id or original.id,
            primary_category=original.primary_category or category,
            secondary_categories=original.secondary_categories,
            route_roles=roles,
            experience_tags=list(dict.fromkeys([*original.experience_tags, *candidate.tags])),
            lat=candidate.lat,
            lng=candidate.lng,
            avg_price=candidate.avg_price or original.avg_price,
            price_min=candidate.avg_price or original.price_min,
            price_max=candidate.avg_price or original.price_max,
            rating=candidate.rating,
            review_count=candidate.review_count,
            popularity=original.popularity,
            crowd_level=original.crowd_level,
            queue_minutes=candidate.queue_minutes,
            live_crowd_level=candidate.live_crowd_level,
            visit_duration_minutes=original.visit_duration_minutes,
            open_time=original.open_time,
            close_time=original.close_time,
            last_entry_time=original.last_entry_time,
            open_hours=original.open_hours,
            suitable_time_slots=original.suitable_time_slots,
            tags=list(dict.fromkeys([*original.tags, *candidate.tags])),
            negative_tags=[],
            family_friendly=original.family_friendly,
            couple_friendly=original.couple_friendly,
            friends_friendly=original.friends_friendly,
            solo_friendly=original.solo_friendly,
            elderly_friendly=original.elderly_friendly,
            rainy_day_score=original.rainy_day_score,
            budget_friendly=original.budget_friendly,
            photo_friendly=original.photo_friendly,
            food_nearby=original.food_nearby,
            night_activity=original.night_activity,
            indoor=original.indoor,
            walking_intensity=original.walking_intensity,
            recommended_transport=original.recommended_transport,
            meal_type=original.meal_type,
            transit_hub_nearby=original.transit_hub_nearby,
            cover_image_url=original.cover_image_url,
            highlight_text=f"地图实时补充：{candidate.name}",
            highlight_text_tags=candidate.tags,
            ugc_tip=original.ugc_tip,
        )

    def _replacement_score(self, original: POI, candidate: POI, origin: GeoPoint, request: ReplanRequest, event_payload: dict) -> float:
        status = self._live_status_for_poi(candidate, event_payload)
        leg = self.map_provider.get_live_travel_time(origin, GeoPoint(lat=candidate.lat, lng=candidate.lng), self._transport_mode(candidate), event_payload=event_payload)
        score = self._replacement_role_score(original, candidate) * 3
        score += max(0, 1 - min(candidate.queue_minutes, 90) / 90) * 2
        score += max(0, 1 - min(leg.travel_minutes, 60) / 60) * 1.5
        score += max(0, candidate.rating - 3.5) * 0.4
        if request.event_type == "user_tired":
            score += (1.2 if candidate.walking_intensity == "low" else 0) + (0.8 if candidate.indoor else 0)
        if request.event_type == "weather_change":
            score += 1.5 if candidate.indoor else -1
        if status.status in {"closed", "unavailable", "sold_out"}:
            score -= 10
        return score

    def _replacement_role_score(self, original: POI, candidate: POI) -> float:
        role_overlap = len(set(original.route_roles) & set(candidate.route_roles))
        category_hit = original.primary_category and original.primary_category == candidate.primary_category
        meal_hit = original.meal_type != "non_meal" and original.meal_type == candidate.meal_type
        return role_overlap + (1 if category_hit else 0) + (0.7 if meal_hit else 0)

    def _rebuild_future_stops(
        self,
        completed_stops: list[RouteStop],
        future_pois: list[POI],
        route: Route,
        request: ReplanRequest,
        event_payload: dict,
    ) -> list[RouteStop]:
        if not future_pois:
            return []
        current_minutes = self._parse_time(request.current_time or (completed_stops[-1].end_time if completed_stops else future_pois[0].open_time))
        origin = self._origin_from_request_or_route(request, completed_stops, future_pois[0])
        rebuilt: list[RouteStop] = []
        for poi in future_pois:
            mode = self._transport_mode(poi)
            leg = self.map_provider.get_live_travel_time(origin, GeoPoint(lat=poi.lat, lng=poi.lng), mode, event_payload=event_payload)
            start = current_minutes + leg.travel_minutes
            end = start + poi.queue_minutes + poi.visit_duration_minutes
            rebuilt.append(self._stop_from_poi(poi, start, end, leg.travel_minutes, leg.distance_km, leg.transport_mode, route.objective))
            current_minutes = end
            origin = GeoPoint(lat=poi.lat, lng=poi.lng)
        return rebuilt

    def _stop_from_poi(
        self,
        poi: POI,
        start_minutes: int,
        end_minutes: int,
        travel_minutes: int,
        distance_km: float,
        transport_mode: str,
        objective: str,
    ) -> RouteStop:
        return RouteStop(
            poi_id=poi.id,
            name=poi.name,
            category=poi.category,
            primary_category=poi.primary_category,
            secondary_categories=poi.secondary_categories,
            route_roles=poi.route_roles,
            experience_tags=poi.experience_tags,
            district=poi.district,
            address=poi.address,
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
            travel_minutes_from_previous=travel_minutes,
            distance_km_from_previous=distance_km,
            transport_mode_from_previous=transport_mode,
            reason=f"根据实时{self.map_provider.source}数据调整，继续匹配{objective}目标",
        )

    def _refresh_route_metrics(self, route: Route, request: ReplanRequest, poi_by_id: dict[str, POI]) -> None:
        route.total_cost_per_person = sum(stop.estimated_cost for stop in route.stops)
        route.total_queue_minutes = sum(stop.queue_minutes for stop in route.stops)
        route.total_travel_minutes = sum(stop.travel_minutes_from_previous or 0 for stop in route.stops)
        route.total_distance_km = round(sum(stop.distance_km_from_previous or 0 for stop in route.stops), 1)
        route.total_duration_minutes = self._route_elapsed_minutes(route.stops)
        plan_request = self._plan_request_for_replan(route, request, poi_by_id)
        route.score_breakdown = self.scoring_service.score(route.stops, route.objective, plan_request, poi_by_id)
        route.score = self.scoring_service.overall_score(route.score_breakdown, route.objective, route.stops, plan_request, poi_by_id)

    def _plan_request_for_replan(self, route: Route, request: ReplanRequest, poi_by_id: dict[str, POI]) -> RoutePlanRequest:
        intent = request.intent or Intent(
            city=self._route_city(route, poi_by_id),
            start_time=route.stops[0].start_time if route.stops else "14:00",
            duration_hours=max(1, round(route.total_duration_minutes / 60)),
            budget_per_person=max(route.total_cost_per_person, 1),
            preferences=[route.objective],
        )
        profile = request.user_profile or UserProfile(user_id="replan_user", preferences=[route.objective])
        return RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=list(poi_by_id.values()))

    def _traffic_warnings(self, stops: list[RouteStop], event_payload: dict) -> list[str]:
        warnings = []
        if event_payload.get("event_type") != "traffic_jam":
            return warnings
        multiplier = float(event_payload.get("traffic_multiplier", 1.0) or 1.0)
        if multiplier >= self.TRAFFIC_WARNING_MULTIPLIER:
            warnings.append(f"交通拥堵已计入后续路程，预计通行时间约为平时 {multiplier:.1f} 倍。")
        return warnings

    def _replacement_reason(self, status: ExternalPOIStatus, request: ReplanRequest) -> str:
        if status.status in {"closed", "unavailable", "sold_out"}:
            return status.reason or "原 POI 实时状态不可用"
        if request.event_type == "queue_spike":
            return "原 POI 实时排队过长"
        if request.event_type == "traffic_jam":
            return "原路线交通变慢，改用更顺路点位"
        if request.event_type == "user_tired":
            return "用户状态变化，改为更轻松点位"
        if request.event_type == "weather_change":
            return "天气变化，改为更稳妥点位"
        return request.event_label

    def _status_warning(self, status: ExternalPOIStatus, poi: POI) -> str:
        if status.status in {"closed", "unavailable", "sold_out"}:
            return status.reason or "实时状态不可用"
        if poi.queue_minutes >= self.QUEUE_REPLACE_THRESHOLD:
            return f"实时排队约 {poi.queue_minutes} 分钟"
        if status.live_crowd_level is not None and status.live_crowd_level >= 0.8:
            return "实时人流较高"
        return ""

    def _replan_reason(self, request: ReplanRequest, replacement_used: bool, warnings: list[str]) -> str:
        if replacement_used:
            return f"已根据「{request.event_label}」替换受影响的后续点位，并重新计算时间、排队和交通。"
        if warnings:
            return f"已根据「{request.event_label}」重新评估路线，当前无需替换点位。"
        return f"已接入实时{self.map_provider.source}数据复核，原路线仍是当前更优选择。"

    def _summary(self, route: Route, request: ReplanRequest, replacement_used: bool) -> str:
        action = "动态调整后" if replacement_used else "实时复核后"
        return (
            f"{action}，{route.title}综合评分 {route.score} 分，包含 {len(route.stops)} 个点，"
            f"人均约 {route.total_cost_per_person} 元，排队 {route.total_queue_minutes} 分钟，"
            f"路上约 {route.total_travel_minutes} 分钟。"
        )

    def _poi_for_stop(self, stop: RouteStop, poi_by_id: dict[str, POI]) -> POI:
        poi = poi_by_id.get(stop.poi_id)
        if poi:
            return poi
        return POI(
            id=stop.poi_id,
            name=stop.name,
            city="上海",
            district=stop.district,
            address=stop.address,
            category=stop.category,
            primary_category=stop.primary_category,
            secondary_categories=stop.secondary_categories,
            route_roles=stop.route_roles,
            experience_tags=stop.experience_tags,
            lat=0,
            lng=0,
            avg_price=stop.estimated_cost,
            rating=4.0,
            queue_minutes=stop.queue_minutes,
            visit_duration_minutes=max(30, self._parse_time(stop.end_time) - self._parse_time(stop.start_time) - stop.queue_minutes),
            open_hours=stop.open_hours or "00:00-23:59",
            tags=stop.tags,
            family_friendly=0,
            indoor=stop.indoor,
            walking_intensity=stop.walking_intensity,
            recommended_transport=stop.recommended_transport,
            meal_type=stop.meal_type,
            cover_image_url=stop.cover_image_url,
            highlight_text=stop.highlight_text,
            ugc_tip=stop.ugc_tip,
        )

    def _route_city(self, route: Route, poi_by_id: dict[str, POI]) -> str:
        for stop in route.stops:
            poi = poi_by_id.get(stop.poi_id)
            if poi and poi.city:
                return poi.city
        return "上海"

    def _origin_from_request_or_route(self, request: ReplanRequest, completed_stops: list[RouteStop], fallback: POI) -> GeoPoint:
        if request.current_lat is not None and request.current_lng is not None:
            return GeoPoint(lat=request.current_lat, lng=request.current_lng)
        if request.current_poi_id:
            poi = next((candidate for candidate in self.poi_service.all_pois() if candidate.id == request.current_poi_id), None)
            if poi:
                return GeoPoint(lat=poi.lat, lng=poi.lng)
        if completed_stops:
            poi = next((candidate for candidate in self.poi_service.all_pois() if candidate.id == completed_stops[-1].poi_id), None)
            if poi:
                return GeoPoint(lat=poi.lat, lng=poi.lng)
        return GeoPoint(lat=fallback.lat, lng=fallback.lng)

    def _origin_point(self, previous_stop: RouteStop | None, fallback: POI) -> GeoPoint:
        if previous_stop:
            poi = next((candidate for candidate in self.poi_service.all_pois() if candidate.id == previous_stop.poi_id), None)
            if poi:
                return GeoPoint(lat=poi.lat, lng=poi.lng)
        return GeoPoint(lat=fallback.lat, lng=fallback.lng)

    def _transport_mode(self, poi: POI) -> str:
        if poi.recommended_transport:
            return poi.recommended_transport[0]
        return "walk" if poi.walking_intensity != "high" else "metro"

    def _sources(self, route: Route, provider_source: str) -> list[str]:
        sources = {provider_source}
        for stop in route.stops:
            if stop.poi_id.startswith("mock_") or stop.poi_id.startswith("external_"):
                sources.add(provider_source)
            else:
                sources.add("local")
        return sorted(sources)

    def _parse_time(self, value: str) -> int:
        try:
            hour, minute = value.split(":", 1)
            return int(hour) * 60 + int(minute)
        except ValueError:
            return 14 * 60

    def _format_time(self, minutes: int) -> str:
        minutes = minutes % (24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _route_elapsed_minutes(self, stops: list[RouteStop]) -> int:
        if not stops:
            return 0
        start = self._parse_time(stops[0].start_time)
        end = self._parse_time(stops[-1].end_time)
        if end < start:
            end += 24 * 60
        return end - start
