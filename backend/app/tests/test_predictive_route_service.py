from app.schemas.user import UserProfile
from app.services.predictive_route_service import PredictiveRouteRequest, PredictiveRouteService
from app.schemas.route import RoutePlanResponse


def _overlap_ratio(route_a, route_b) -> float:
    ids_a = {stop.poi_id for stop in route_a.stops}
    ids_b = {stop.poi_id for stop in route_b.stops}
    return len(ids_a & ids_b) / max(1, min(len(ids_a), len(ids_b)))


def test_mock_weather_loads_shanghai_and_beijing() -> None:
    service = PredictiveRouteService()

    shanghai = service.weather_for("上海", "rainy")
    beijing = service.weather_for("北京", "sunny")

    assert shanghai["condition"] == "rainy"
    assert beijing["condition"] == "sunny"


def test_weather_preferences_follow_condition() -> None:
    service = PredictiveRouteService()

    rainy = service.preferences_from_weather(service.weather_for("上海", "rainy"))
    sunny = service.preferences_from_weather(service.weather_for("北京", "sunny"))

    assert {"室内", "雨天", "少走路"} <= set(rainy)
    assert {"citywalk", "拍照", "自然风景"} <= set(sunny)


def test_profile_user_gets_three_routes_with_balanced_and_profile_objectives() -> None:
    response = PredictiveRouteService().generate(
        PredictiveRouteRequest(
            user_id="user_demo",
            city="上海",
            weather_scenario="sunny",
            user_profile=UserProfile(
                user_id="profiled",
                tags=["吃好", "citywalk"],
                preferences=["吃好", "citywalk"],
                preference_weights={},
            ),
        )
    )

    objectives = {route.objective for route in response.routes}
    assert len(response.routes) == 3
    assert "balanced" in objectives
    assert {"food_first", "photo_citywalk"} & objectives
    assert all(2 <= len(route.stops) <= 4 for route in response.routes)


def test_seed_profile_user_is_treated_as_profiled_user() -> None:
    response = PredictiveRouteService().generate(
        PredictiveRouteRequest(
            user_id="user_001",
            city="上海",
            weather_scenario="rainy",
        )
    )

    assert len(response.routes) == 3
    assert "balanced" in {route.objective for route in response.routes}


def test_new_user_gets_top_diverse_routes_without_default_profile() -> None:
    response = PredictiveRouteService().generate(
        PredictiveRouteRequest(
            user_id="brand_new_user",
            city="北京",
            weather_scenario="cloudy",
        )
    )

    assert len(response.routes) == 3
    assert len({route.objective for route in response.routes}) == 3
    assert all(2 <= len(route.stops) <= 4 for route in response.routes)
    for index, route in enumerate(response.routes):
        for other in response.routes[index + 1 :]:
            assert _overlap_ratio(route, other) <= 0.7
            assert {stop.poi_id for stop in route.stops} != {stop.poi_id for stop in other.stops}


def test_predictive_route_service_returns_best_partial_result() -> None:
    service = PredictiveRouteService()
    partial = RoutePlanResponse.model_construct(routes=[object(), object()])
    service.route_service.generate_routes = lambda _request: partial

    response = service.generate(PredictiveRouteRequest(user_id="partial", city="上海"))

    assert response is partial
    assert len(response.routes) == 2


def test_rainy_predictive_routes_include_indoor_option() -> None:
    response = PredictiveRouteService().generate(
        PredictiveRouteRequest(
            user_id="rainy_user",
            city="上海",
            weather_scenario="rainy",
        )
    )

    assert response.routes
    assert any(
        route.objective == "indoor_rainy" or any(stop.indoor for stop in route.stops)
        for route in response.routes
    )


def test_predictive_routes_keep_mock_map_leg_fields() -> None:
    response = PredictiveRouteService().generate(
        PredictiveRouteRequest(
            user_id="transit_user",
            city="上海",
            weather_scenario="sunny",
            start_lat=31.2304,
            start_lng=121.4737,
        )
    )

    first_stop = response.routes[0].stops[0]
    assert first_stop.travel_minutes_from_previous is not None
    assert first_stop.distance_km_from_previous is not None
    assert first_stop.transport_mode_from_previous is not None
    assert first_stop.polyline_from_previous
    assert first_stop.route_leg_source_from_previous == "mock_map"
    assert first_stop.route_steps_from_previous
