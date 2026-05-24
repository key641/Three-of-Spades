from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService


def _plan(intent: Intent):
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    return RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    )


def test_generate_route_candidates() -> None:
    response = _plan(Intent())

    assert len(response.routes) > 3
    assert "balanced" in {route.objective for route in response.routes}
    assert all(1 <= len(route.stops) <= 5 for route in response.routes)
    assert all(route.score == 0 for route in response.routes)


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


def test_same_objective_candidates_are_not_identical() -> None:
    response = _plan(Intent())

    for objective in {route.objective for route in response.routes}:
        sequences = [tuple(stop.poi_id for stop in route.stops) for route in response.routes if route.objective == objective]
        assert len(sequences) == len(set(sequences))


def test_route_stop_contains_enriched_poi_fields() -> None:
    response = _plan(Intent(start_lat=31.2304, start_lng=121.4737))
    first_stop = response.routes[0].stops[0]

    assert first_stop.lat is not None
    assert first_stop.lng is not None
    assert first_stop.meal_type
    assert first_stop.open_hours
    assert first_stop.last_entry_time
    assert first_stop.walking_intensity
    assert first_stop.cover_image_url
    assert first_stop.highlight_text
    assert first_stop.travel_minutes_from_previous is not None
    assert first_stop.distance_km_from_previous is not None
    assert first_stop.transport_mode_from_previous is not None
    assert first_stop.polyline_from_previous
    assert first_stop.amap_distance_meters_from_previous is not None
    assert first_stop.amap_duration_minutes_from_previous is not None
    assert first_stop.route_leg_source_from_previous in {"amap", "fallback"}
    assert first_stop.reason
