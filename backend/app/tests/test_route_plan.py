from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.strategy_service import StrategyService


def _plan(intent: Intent, message: str = ""):
    profile = ProfileService().get_profile("user_demo")
    strategy_tags = StrategyService().infer_tags(message or " ".join(intent.preferences), intent, profile)
    strategy_weights = ProfileService().build_strategy_weights(intent, profile, strategy_tags)
    pois = POIService().search(intent, user_profile=profile, strategy_tags=strategy_tags)
    return RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, strategy_weights=strategy_weights, strategy_tags=strategy_tags, candidate_pois=pois)
    )


def test_generate_route_candidates() -> None:
    response = _plan(Intent())

    assert len(response.routes) == 3
    assert "balanced" in {route.objective for route in response.routes}
    assert response.routes[0].objective != "balanced"
    assert len({route.objective for route in response.routes}) == len(response.routes)
    assert all(1 <= len(route.stops) <= 5 for route in response.routes)
    assert all(0 < route.score <= 100 for route in response.routes)
    assert all(route.score_breakdown.preference > 0 for route in response.routes)


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
    assert all(1 <= len(route.stops) <= 3 for route in short_routes)
    assert all(3 <= len(route.stops) <= 5 for route in long_routes)
    assert all(route.total_duration_minutes <= 180 for route in short_routes)
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

    assert "photo_food" in objectives
    assert "food_first" in objectives
    assert "balanced" in objectives
    assert "low_queue" not in objectives
    assert objectives[0] != "balanced"


def test_nature_intent_generates_nature_route_and_balanced() -> None:
    response = _plan(Intent(preferences=["自然风景", "少排队"]), message="想看自然风景，轻松半日游，少排队")
    objectives = [route.objective for route in response.routes]

    assert "nature_relax" in objectives
    assert "balanced" in objectives
    assert "low_queue" not in objectives


def test_returns_one_top_route_per_objective() -> None:
    response = _plan(Intent())

    assert all(route.route_id == f"route_{route.objective}_best" for route in response.routes)
    assert all("推荐" in route.title for route in response.routes)
    assert all("优势是" in route.summary for route in response.routes)


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


def test_photo_citywalk_route_has_photo_or_main_activity_structure() -> None:
    response = _plan(Intent(preferences=["citywalk", "拍照"]))
    photo_route = next(route for route in response.routes if route.objective == "photo_citywalk")

    assert any("photo_stop" in stop.route_roles for stop in photo_route.stops)
    assert any("main_activity" in stop.route_roles for stop in photo_route.stops)


def test_multi_city_route_generation_has_usable_candidates() -> None:
    for city in ["北京", "杭州", "成都"]:
        response = _plan(Intent(city=city, preferences=["咖啡", "拍照"], duration_hours=6))

        assert 1 <= len(response.routes) <= 3
        assert all(route.stops for route in response.routes)
        assert all(stop.district for route in response.routes for stop in route.stops)


def test_indoor_rainy_route_has_indoor_main_activity() -> None:
    response = _plan(Intent(preferences=["室内", "雨天"]))
    indoor_route = next(route for route in response.routes if route.objective == "indoor_rainy")

    assert any(stop.indoor and "main_activity" in stop.route_roles for stop in indoor_route.stops)


def test_chongqing_half_day_defaults_to_one_meal_or_coffee_node() -> None:
    response = _plan(
        Intent(city="重庆", duration_hours=4, preferences=["室内", "拍照", "吃好", "citywalk"]),
        message="我打算下午和朋友在重庆半日游，不希望一直在室外，能够打卡地标景点还能出片，吃点重庆特色美食。",
    )

    assert response.routes
    for route in response.routes:
        has_coffee = any(stop.category == "cafe" or stop.meal_type == "cafe" for stop in route.stops)
        has_meal = any(stop.category == "restaurant" or stop.meal_type in {"local_food", "fine_dining"} for stop in route.stops)
        assert not (has_coffee and has_meal)
        if has_coffee or has_meal:
            assert any("main_activity" in stop.route_roles or "photo_stop" in stop.route_roles for stop in route.stops)


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
