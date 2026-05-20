from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.schemas.user import StrategyWeights
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService


def test_generate_routes() -> None:
    intent = Intent()
    profile_service = ProfileService()
    profile = profile_service.get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    )
    assert len(response.routes) == 3
    assert [route.objective for route in response.routes] == ["balanced", "low_queue", "budget"]
    assert all(1 <= len(route.stops) <= 5 for route in response.routes)
    assert all(route.total_travel_minutes >= 0 for route in response.routes)


def test_empty_candidates_return_empty_routes() -> None:
    profile = ProfileService().get_profile("user_demo")
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=Intent(), user_profile=profile, candidate_pois=[])
    )

    assert response.routes == []


def test_short_duration_does_not_exceed_time_window() -> None:
    intent = Intent(duration_hours=3)
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    )

    assert response.routes
    assert all(route.total_duration_minutes <= 180 for route in response.routes)


def test_budget_route_cost_is_lowest_for_budget_preference() -> None:
    intent = Intent(preferences=["更省钱"], budget_per_person=100)
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    response = RouteService().generate_routes(
        RoutePlanRequest(
            intent=intent,
            user_profile=profile,
            strategy_weights=StrategyWeights(budget=0.35),
            candidate_pois=pois,
        )
    )

    costs = {route.objective: route.total_cost_per_person for route in response.routes}
    assert "budget" in costs
    assert costs["budget"] == min(costs.values())


def test_low_queue_route_has_lowest_queue_for_queue_preference() -> None:
    intent = Intent(preferences=["少排队"])
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    response = RouteService().generate_routes(
        RoutePlanRequest(
            intent=intent,
            user_profile=profile,
            strategy_weights=StrategyWeights(queue=0.35),
            candidate_pois=pois,
        )
    )

    queues = {route.objective: route.total_queue_minutes for route in response.routes}
    assert "low_queue" in queues
    assert queues["low_queue"] == min(queues.values())


def test_food_preference_adds_food_first_route() -> None:
    intent = Intent(preferences=["吃好"])
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    )

    food_route = next(route for route in response.routes if route.objective == "food_first")
    assert any(stop.category in {"restaurant", "cafe", "market"} for stop in food_route.stops)


def test_start_location_adds_first_leg_travel_fields() -> None:
    intent = Intent(start_lat=31.2304, start_lng=121.4737)
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    )

    first_stop = response.routes[0].stops[0]
    assert first_stop.travel_minutes_from_previous is not None
    assert first_stop.distance_km_from_previous is not None
    assert first_stop.transport_mode_from_previous is not None
