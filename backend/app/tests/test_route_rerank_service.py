from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import Route, RoutePlanRequest, RouteScoreBreakdown, RouteStop
from app.schemas.user import UserProfile
from app.services.route_rerank_service import RouteRerankService


def _stop(poi_id: str, category: str = "landmark", roles: list[str] | None = None, cost: int = 80, walk: str = "low") -> RouteStop:
    return RouteStop(
        poi_id=poi_id,
        name=poi_id,
        category=category,
        primary_category="food" if category in {"restaurant", "cafe"} else category,
        route_roles=roles or ["main_activity"],
        start_time="14:00",
        end_time="15:00",
        estimated_cost=cost,
        queue_minutes=5,
        tags=[],
        walking_intensity=walk,
        travel_minutes_from_previous=8,
        distance_km_from_previous=0.8,
        transport_mode_from_previous="metro",
    )


def _route(route_id: str, objective: str, stops: list[RouteStop], score: int = 80) -> Route:
    return Route(
        route_id=route_id,
        title=route_id,
        objective=objective,
        summary="test",
        total_duration_minutes=120,
        total_cost_per_person=sum(stop.estimated_cost for stop in stops),
        total_queue_minutes=sum(stop.queue_minutes for stop in stops),
        total_travel_minutes=sum(stop.travel_minutes_from_previous or 0 for stop in stops),
        total_distance_km=sum(stop.distance_km_from_previous or 0 for stop in stops),
        score=score,
        score_breakdown=RouteScoreBreakdown(quality=80, queue=80, budget=80, distance=80, preference=80),
        stops=stops,
        reasons=[],
    )


def _poi(stop: RouteStop) -> POI:
    return POI(
        id=stop.poi_id,
        name=stop.name,
        city="上海",
        category=stop.category,
        primary_category=stop.primary_category,
        route_roles=stop.route_roles,
        lat=31.2,
        lng=121.4,
        avg_price=stop.estimated_cost,
        rating=4.5,
        queue_minutes=stop.queue_minutes,
        visit_duration_minutes=60,
        open_hours="09:00-22:00",
        family_friendly=0.5,
        indoor=stop.indoor,
    )


def _poi_by_id(routes: list[Route]) -> dict[str, POI]:
    return {stop.poi_id: _poi(stop) for route in routes for stop in route.stops}


def test_budget_sensitive_user_prefers_lower_cost_route() -> None:
    service = RouteRerankService()
    cheap = _route("cheap", "budget", [_stop("cheap_main", cost=40), _stop("cheap_meal", "restaurant", ["meal"], cost=50)])
    expensive = _route("expensive", "budget", [_stop("exp_main", cost=240), _stop("exp_meal", "restaurant", ["meal"], cost=260)])
    request = RoutePlanRequest(intent=Intent(budget_per_person=120, preferences=["更省钱"]), user_profile=UserProfile(user_id="u", budget_sensitivity=0.9))

    assert service.score(cheap, request, _poi_by_id([cheap, expensive])).score > service.score(expensive, request, _poi_by_id([cheap, expensive])).score


def test_low_walking_user_prefers_short_transit_route() -> None:
    service = RouteRerankService()
    easy = _route("easy", "low_walking", [_stop("easy_main"), _stop("easy_rest", "cafe", ["coffee_break", "rest_stop"])])
    hard_stop = _stop("hard_main", walk="high")
    hard_stop.distance_km_from_previous = 2.4
    hard_stop.transport_mode_from_previous = "walk"
    hard = _route("hard", "low_walking", [hard_stop, _stop("hard_rest", "cafe", ["coffee_break", "rest_stop"])])
    request = RoutePlanRequest(intent=Intent(preferences=["少走路"]), user_profile=UserProfile(user_id="u", walking_tolerance=0.1))

    assert service.score(easy, request, _poi_by_id([easy, hard])).score > service.score(hard, request, _poi_by_id([easy, hard])).score


def test_bad_meal_sequence_penalized_unless_food_crawl() -> None:
    service = RouteRerankService()
    route = _route(
        "food_chain",
        "food_first",
        [
            _stop("meal_a", "restaurant", ["meal"]),
            _stop("meal_b", "restaurant", ["meal"]),
            _stop("coffee", "cafe", ["coffee_break"]),
        ],
    )
    normal = RoutePlanRequest(intent=Intent(preferences=["吃好"]), user_profile=UserProfile(user_id="u"))
    crawl = RoutePlanRequest(intent=Intent(preferences=["美食路线", "扫街"]), user_profile=UserProfile(user_id="u"))

    assert service.score(route, crawl, _poi_by_id([route])).score > service.score(route, normal, _poi_by_id([route])).score


def test_rerank_prefers_diverse_route_after_first_selection() -> None:
    service = RouteRerankService()
    first = _route("first", "photo_citywalk", [_stop("a"), _stop("b")], score=90)
    overlap = _route("overlap", "balanced", [_stop("a"), _stop("b")], score=89)
    diverse = _route("diverse", "budget", [_stop("c"), _stop("d")], score=82)
    request = RoutePlanRequest(intent=Intent(), user_profile=UserProfile(user_id="u", novelty_preference=0.9))

    overlap_score = service.score(overlap, request, _poi_by_id([first, overlap, diverse]), selected_routes=[first]).score
    diverse_score = service.score(diverse, request, _poi_by_id([first, overlap, diverse]), selected_routes=[first]).score

    assert diverse_score > overlap_score
