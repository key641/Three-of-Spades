from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.amap_service import GeoPoint, RouteLeg
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.strategy_service import StrategyService


def _plan(intent: Intent, message: str = ""):
    profile = ProfileService().get_profile("user_demo")
    strategy_tags = StrategyService().infer_tags(message or " ".join(intent.preferences), intent, profile)
    strategy_weights = ProfileService().build_strategy_weights(intent, profile, strategy_tags)
    for limit, relax_preferences in [(60, False), (90, True), (120, True)]:
        pois = POIService().search(
            intent,
            user_profile=profile,
            strategy_tags=strategy_tags,
            limit=limit,
            relax_preferences=relax_preferences,
        )
        response = RouteService().generate_routes(
            RoutePlanRequest(
                intent=intent.model_copy(deep=True),
                user_profile=profile,
                strategy_weights=strategy_weights,
                strategy_tags=strategy_tags,
                candidate_pois=pois,
            )
        )
        if len(response.routes) == 3:
            return response
    return response


def test_generate_route_candidates() -> None:
    response = _plan(Intent())
    all_stop_ids = [stop.poi_id for route in response.routes for stop in route.stops]

    assert len(response.routes) == 3
    assert len({route.objective for route in response.routes}) == len(response.routes)
    assert all(3 <= len(route.stops) <= 5 for route in response.routes)
    assert len({tuple(sorted(stop.poi_id for stop in route.stops)) for route in response.routes}) == len(response.routes)
    assert len(all_stop_ids) == len(set(all_stop_ids))
    assert all(len({stop.primary_category or stop.category for stop in route.stops}) >= 2 for route in response.routes)
    assert all(0 < route.score <= 100 for route in response.routes)
    assert all(route.score_breakdown.preference > 0 for route in response.routes)
    assert all(
        stop.transport_mode_from_previous
        and stop.travel_minutes_from_previous is not None
        and stop.distance_km_from_previous is not None
        and stop.polyline_from_previous
        and stop.route_steps_from_previous
        for route in response.routes
        for stop in route.stops
    )


def test_empty_candidates_return_empty_routes() -> None:
    profile = ProfileService().get_profile("user_demo")
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=Intent(), user_profile=profile, candidate_pois=[])
    )

    assert response.routes == []


def test_stop_count_follows_duration_window() -> None:
    short_routes = _plan(Intent(duration_hours=3)).routes
    long_routes = _plan(Intent(duration_hours=8)).routes

    assert short_routes
    assert long_routes
    assert all(3 <= len(route.stops) <= 3 for route in short_routes)
    assert all(3 <= len(route.stops) <= 5 for route in long_routes)
    assert all(route.total_duration_minutes <= 300 for route in short_routes)
    assert all(route.total_duration_minutes <= 480 for route in long_routes)


def test_food_or_coffee_preference_generates_food_candidates() -> None:
    response = _plan(Intent(preferences=["咖啡"]))

    assert "food_first" in {route.objective for route in response.routes}
    assert any(
        stop.category == "cafe" or stop.meal_type == "cafe"
        for route in response.routes
        for stop in route.stops
    )


def test_low_walking_preference_generates_low_walking_candidates() -> None:
    response = _plan(Intent(preferences=["少走路"]))
    low_walking_routes = [route for route in response.routes if route.objective == "low_walking"]

    assert low_walking_routes
    assert all(
        sum(1 for stop in route.stops if stop.walking_intensity == "low") >= len(route.stops) - 1
        for route in low_walking_routes
    )


def test_indoor_rainy_preference_generates_indoor_candidates() -> None:
    response = _plan(Intent(preferences=["室内", "雨天"]))
    indoor_routes = [route for route in response.routes if route.objective == "indoor_rainy"]

    assert indoor_routes
    assert all(any(stop.indoor for stop in route.stops) for route in indoor_routes)


def test_photo_citywalk_preference_generates_photo_candidates() -> None:
    response = _plan(Intent(preferences=["citywalk", "拍照"]))
    photo_routes = [route for route in response.routes if route.objective == "photo_citywalk"]

    assert photo_routes
    assert any(
        any(tag in {"拍照", "夜景", "经典", "文艺"} for tag in stop.tags)
        for route in photo_routes
        for stop in route.stops
    )


def test_photo_food_strong_intent_beats_low_queue_objective() -> None:
    response = _plan(
        Intent(preferences=["拍照", "吃好", "少排队"]),
        message="饭店拍照必须好看，吃美食，也希望少排队",
    )
    objectives = [route.objective for route in response.routes]
    all_stop_ids = [stop.poi_id for route in response.routes for stop in route.stops]

    assert "photo_food" in objectives
    assert "food_first" in objectives
    assert "low_queue" not in objectives
    assert objectives[0] != "balanced"
    assert len(all_stop_ids) == len(set(all_stop_ids))


def test_nature_intent_generates_nature_route_and_balanced() -> None:
    response = _plan(Intent(preferences=["自然风景", "少排队"]), message="想看自然风景，轻松半日游，少排队")
    objectives = [route.objective for route in response.routes]

    assert "nature_relax" in objectives
    assert "balanced" in objectives
    assert "low_queue" not in objectives


def test_returns_one_top_route_per_objective() -> None:
    response = _plan(Intent())

    assert all(route.route_id.startswith(f"route_{route.objective}_") for route in response.routes)
    assert all("推荐" in route.title for route in response.routes)
    assert all("优势是" in route.summary for route in response.routes)


def test_final_routes_do_not_share_any_pois() -> None:
    response = _plan(Intent(preferences=["citywalk", "拍照", "吃好"]))
    all_stop_ids = [stop.poi_id for route in response.routes for stop in route.stops]

    assert len(all_stop_ids) == len(set(all_stop_ids))


def test_simple_route_can_relax_to_two_stops_but_never_one() -> None:
    profile = ProfileService().get_profile("user_demo")
    intent = Intent(preferences=["简单点", "轻松"], duration_hours=4)
    pois = POIService().search(intent, user_profile=profile, limit=12)
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois),
        allow_min_stops_fallback=True,
    )

    assert response.routes
    assert all(2 <= len(route.stops) <= 3 for route in response.routes)


def test_internal_candidate_generation_uses_more_than_four_routes_per_objective() -> None:
    profile = ProfileService().get_profile("user_demo")
    intent = Intent()
    pois = POIService().search(intent, user_profile=profile)
    request = RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    routes = RouteService()._build_candidates_for_objective(pois, "balanced", request)

    assert 5 <= len(routes) <= RouteService.INTERNAL_CANDIDATES_PER_OBJECTIVE
    assert len({tuple(stop.poi_id for stop in route.stops) for route in routes}) == len(routes)


def test_total_internal_candidate_generation_stays_in_target_range() -> None:
    profile = ProfileService().get_profile("user_demo")
    intent = Intent()
    pois = POIService().search(intent, user_profile=profile)
    request = RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    service = RouteService()
    objectives = service._select_objectives(request)
    candidates = [
        route
        for objective in objectives
        for route in service._build_candidates_for_objective(pois, objective, request)
    ]

    assert 10 <= len(candidates) <= len(objectives) * RouteService.INTERNAL_CANDIDATES_PER_OBJECTIVE


def test_start_seeds_cover_multiple_categories_and_roles() -> None:
    profile = ProfileService().get_profile("user_demo")
    intent = Intent(preferences=["citywalk", "拍照"])
    pois = POIService().search(intent, user_profile=profile)
    request = RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    service = RouteService()
    seeds = service._diverse_start_seeds(service._start_candidates(pois, "photo_citywalk", request), 10)

    assert len({poi.category for poi in seeds}) >= 4
    assert any("main_activity" in poi.route_roles for poi in seeds)
    assert any("photo_stop" in poi.route_roles for poi in seeds)


def test_beam_route_is_not_plain_top_poi_sequence() -> None:
    profile = ProfileService().get_profile("user_demo")
    intent = Intent(start_lat=31.2304, start_lng=121.4737, preferences=["citywalk", "拍照"])
    pois = POIService().search(intent, user_profile=profile)
    request = RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    service = RouteService()
    routes = service._build_candidates_for_objective(pois, "photo_citywalk", request)
    assert routes

    top_poi_ids = [poi.id for poi in service._start_candidates(pois, "photo_citywalk", request)[: len(routes[0].stops)]]
    first_route_ids = [stop.poi_id for stop in routes[0].stops]

    assert first_route_ids != top_poi_ids


def test_generate_routes_emits_each_selected_route_incrementally() -> None:
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(Intent(), user_profile=profile)
    emitted = []

    response = RouteService().generate_routes(
        RoutePlanRequest(intent=Intent(), user_profile=profile, candidate_pois=pois),
        on_route=emitted.append,
    )

    assert [route.route_id for route in emitted] == [route.route_id for route in response.routes]
    assert len(emitted) >= 1


def test_route_stop_contains_enriched_poi_fields() -> None:
    response = _plan(Intent(start_lat=31.2304, start_lng=121.4737))
    first_stop = response.routes[0].stops[0]

    assert first_stop.lat is not None
    assert first_stop.lng is not None
    assert first_stop.district
    assert first_stop.business_area
    assert first_stop.meal_type
    assert first_stop.open_hours
    assert first_stop.last_entry_time
    assert first_stop.walking_intensity
    assert first_stop.primary_category
    assert first_stop.route_roles
    assert first_stop.experience_tags is not None
    assert first_stop.cover_image_url
    assert first_stop.highlight_text
    assert first_stop.travel_minutes_from_previous is not None
    assert first_stop.distance_km_from_previous is not None
    assert first_stop.transport_mode_from_previous is not None
    assert first_stop.polyline_from_previous
    assert first_stop.amap_distance_meters_from_previous is not None
    assert first_stop.amap_duration_minutes_from_previous is not None
    assert first_stop.route_leg_source_from_previous in {"amap", "fallback", "mock_map"}
    assert first_stop.route_steps_from_previous
    assert first_stop.reason


def test_wukang_area_shopping_citywalk_uses_store_categories() -> None:
    response = _plan(Intent(city="上海", preferences=["武康路", "逛店", "书店", "买手店", "citywalk"], duration_hours=4))
    store_categories = {"boutique", "bookstore", "lifestyle_store", "toy_collectible", "sports_outdoor", "beauty_retail", "design_store"}

    assert response.routes
    assert any(stop.category in store_categories for route in response.routes for stop in route.stops)
    assert any("武康路" in stop.business_area for route in response.routes for stop in route.stops)


def test_citywalk_food_route_avoids_duplicate_coffee_and_keeps_main_activity() -> None:
    response = _plan(Intent(preferences=["citywalk", "吃好", "少排队"], avoid_tags=["人多"], budget_per_person=300))

    for route in response.routes:
        coffee_count = sum(1 for stop in route.stops if "coffee_break" in stop.route_roles)
        assert coffee_count <= 1
        assert any("main_activity" in stop.route_roles for stop in route.stops)
        assert any("meal" in stop.route_roles or "rest_stop" in stop.route_roles for stop in route.stops)


def test_coffee_crawl_can_repeat_coffee_roles() -> None:
    response = _plan(Intent(preferences=["咖啡探店", "咖啡"]))
    food_route = next(route for route in response.routes if route.objective == "food_first")

    assert any("coffee_break" in stop.route_roles for stop in food_route.stops)


def test_night_route_avoids_plain_cafes_without_explicit_coffee_intent() -> None:
    response = _plan(Intent(start_time="20:00", duration_hours=4, preferences=["晚上", "夜景"]))

    assert response.routes
    assert "night_friendly" in {route.objective for route in response.routes}
    assert all(
        stop.category != "cafe" and stop.meal_type != "cafe" and "coffee_break" not in stop.route_roles
        for route in response.routes
        for stop in route.stops
    )
    assert any(
        stop.category in {"night_view", "theater", "landmark", "shopping"} or "night_end" in stop.route_roles
        for route in response.routes
        for stop in route.stops
    )


def test_explicit_night_coffee_can_use_coffee_theme_without_one_stop_routes() -> None:
    response = _plan(Intent(start_time="20:00", duration_hours=4, preferences=["咖啡探店", "咖啡"]))

    assert response.routes
    for route in response.routes:
        coffee_count = sum(
            1
            for stop in route.stops
            if stop.category == "cafe" or stop.meal_type == "cafe" or "coffee_break" in stop.route_roles
        )
        assert coffee_count >= 1
        assert len(route.stops) >= 3


def test_photo_citywalk_route_has_photo_or_main_activity_structure() -> None:
    response = _plan(Intent(preferences=["citywalk", "拍照"]))
    photo_route = next(route for route in response.routes if route.objective == "photo_citywalk")

    assert any("photo_stop" in stop.route_roles for stop in photo_route.stops)
    assert any("main_activity" in stop.route_roles for stop in photo_route.stops)


def test_unsupported_cities_do_not_generate_mock_routes() -> None:
    for city in ["北京", "杭州", "成都"]:
        response = _plan(Intent(city=city, preferences=["咖啡", "拍照"], duration_hours=6))

        if city == "北京":
            assert len(response.routes) == 3
            assert all(route.stops for route in response.routes)
            assert all(len(route.stops) >= 3 for route in response.routes)
            assert all(stop.district for route in response.routes for stop in route.stops)
        else:
            assert response.routes == []


def test_indoor_rainy_route_has_indoor_main_activity() -> None:
    response = _plan(Intent(preferences=["室内", "雨天"]))
    indoor_route = next(route for route in response.routes if route.objective == "indoor_rainy")

    assert any(stop.indoor and "main_activity" in stop.route_roles for stop in indoor_route.stops)


def test_rainy_hot_context_prefers_indoor_or_low_walking_stops() -> None:
    response = _plan(Intent(preferences=["雨天", "高温", "室内"], duration_hours=4))

    assert response.routes
    assert any(stop.indoor for route in response.routes for stop in route.stops)
    assert all(
        not (not stop.indoor and stop.walking_intensity == "high")
        for route in response.routes
        for stop in route.stops
    )


def test_chongqing_half_day_does_not_use_mock_fallback_routes() -> None:
    response = _plan(
        Intent(city="重庆", duration_hours=4, preferences=["室内", "拍照", "吃好", "citywalk"]),
        message="我打算下午和朋友在重庆半日游，不希望一直在室外，能够打卡地标景点还能出片，吃点重庆特色美食。",
    )

    assert response.routes == []


def test_less_walking_transport_avoids_long_walks() -> None:
    response = _plan(Intent(start_lat=31.2304, start_lng=121.4737, preferences=["少走路"]))

    assert response.routes
    assert all(
        not (
            stop.transport_mode_from_previous == "walk"
            and (stop.distance_km_from_previous or 0) > 1
        )
        for route in response.routes
        for stop in route.stops
    )


def test_beijing_and_shanghai_routes_prefer_public_transit_when_convenient() -> None:
    cases = [
        Intent(city="北京", start_lat=39.9072, start_lng=116.3740, preferences=["吃好", "citywalk"], duration_hours=4, start_time="18:00"),
        Intent(city="上海", start_lat=31.2231, start_lng=121.4466, preferences=["吃好", "citywalk"], duration_hours=4, start_time="18:00"),
    ]

    for intent in cases:
        response = _plan(intent)
        modes = {
            stop.transport_mode_from_previous
            for route in response.routes
            for stop in route.stops
        }
        assert modes & {"metro", "bus"}, intent.city


def test_transport_steps_are_concrete_and_readable() -> None:
    response = _plan(Intent(start_lat=31.2231, start_lng=121.4466, preferences=["吃好", "citywalk"], duration_hours=4))

    assert response.routes
    for route in response.routes:
        for stop in route.stops:
            assert stop.transport_mode_from_previous
            assert stop.travel_minutes_from_previous is not None
            assert stop.distance_km_from_previous is not None
            assert stop.route_leg_source_from_previous
            assert stop.route_steps_from_previous
            joined_steps = " ".join(stop.route_steps_from_previous)
            assert "公共交通" not in joined_steps
            assert any(term in joined_steps for term in ["步行", "乘坐", "打车", "公交", "地铁"])


def test_transit_choice_keeps_taxi_when_public_transit_is_much_slower() -> None:
    service = RouteService()
    profile = ProfileService().get_profile("user_demo")
    request = RoutePlanRequest(intent=Intent(preferences=["少走路"]), user_profile=profile)
    taxi = service.amap_service.route_leg(
        origin=GeoPoint(lat=39.9072, lng=116.3740),
        destination=GeoPoint(lat=39.9095, lng=116.4618),
        mode="taxi",
        departure_time="18:00",
    )
    public = RouteLeg(
        mode="metro",
        distance_meters=taxi.distance_meters,
        duration_minutes=taxi.duration_minutes * 3,
        polyline=taxi.polyline,
        steps=taxi.steps,
        source=taxi.source,
    )

    chosen = service._choose_public_transit_first([public, taxi], request)

    assert chosen.mode == "taxi"
