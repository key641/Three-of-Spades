from app.schemas.intent import Intent
from app.schemas.route import ReplanRequest, RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.replan_service import ReplanService
from app.services.route_service import RouteService
from app.services.map_provider import MockMapProvider


def _route_for_replan(preferences: list[str] | None = None):
    intent = Intent(preferences=preferences or ["citywalk", "吃好"], budget_per_person=300)
    profile = ProfileService().get_profile("user_demo")
    pois = POIService().search(intent, user_profile=profile)
    route = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    ).routes[0]
    return route, intent, profile


def test_queue_spike_replaces_future_poi_and_keeps_completed_stop() -> None:
    route, intent, profile = _route_for_replan(["citywalk", "吃好", "少排队"])
    completed = [route.stops[0].poi_id]
    affected = route.stops[1]

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="queue_spike",
            event_label="排队突然变久",
            current_routes=[route],
            completed_poi_ids=completed,
            current_time=route.stops[0].end_time,
            event_payload={"affected_poi_id": affected.poi_id, "queue_minutes": 90},
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert updated.stops[0].poi_id == completed[0]
    assert affected.poi_id not in [stop.poi_id for stop in updated.stops[1:]]
    assert updated.changed_stops
    assert "替换" in (updated.replan_reason or "")


def test_closed_poi_is_removed_from_future_route() -> None:
    route, intent, profile = _route_for_replan(["室内", "雨天"])
    affected = route.stops[-1]

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="poi_closed",
            event_label="景点临时闭店",
            current_routes=[route],
            event_payload={"affected_poi_id": affected.poi_id, "status": "closed"},
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert affected.poi_id not in [stop.poi_id for stop in updated.stops]
    assert updated.changed_stops
    assert updated.data_sources


def test_traffic_jam_adds_live_warning_and_recalculates_travel() -> None:
    route, intent, profile = _route_for_replan(["citywalk"])

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="traffic_jam",
            event_label="路上交通拥堵",
            current_routes=[route],
            event_payload={"traffic_multiplier": 1.6},
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert updated.live_warnings
    assert updated.total_travel_minutes >= route.total_travel_minutes
    assert updated.score > 0


def test_external_candidate_can_fill_when_local_replacement_is_excluded() -> None:
    route, intent, profile = _route_for_replan(["咖啡"])
    affected = route.stops[0]
    locked = [poi.id for poi in POIService().all_pois(intent.city) if poi.id != affected.poi_id]

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="poi_closed",
            event_label="原地点临时不可用",
            current_routes=[route],
            locked_poi_ids=locked,
            event_payload={
                "affected_poi_id": affected.poi_id,
                "status": "closed",
                "allow_external_candidates": True,
            },
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert any(stop.poi_id.startswith("mock_") for stop in updated.stops)
    assert "mock" in updated.data_sources


def test_replace_poi_replaces_only_target_and_keeps_other_stops() -> None:
    route, intent, profile = _route_for_replan(["citywalk", "拍照"])
    affected = route.stops[1]
    untouched_ids = {stop.poi_id for index, stop in enumerate(route.stops) if index != 1}

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="replace_poi",
            event_label="用户不想去这个点",
            current_routes=[route],
            event_payload={"affected_poi_id": affected.poi_id, "force_replace": True},
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    updated_ids = {stop.poi_id for stop in updated.stops}
    assert affected.poi_id not in updated_ids
    assert untouched_ids.issubset(updated_ids)
    assert updated.changed_stops[0].change_type == "replace"
    assert updated.changed_stops[0].from_poi_id == affected.poi_id


def test_replace_poi_respects_replacement_category() -> None:
    route, intent, profile = _route_for_replan(["citywalk", "拍照"])
    affected = next(stop for stop in route.stops if stop.category != "cafe")

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="replace_poi",
            event_label="换成咖啡馆",
            current_routes=[route],
            event_payload={
                "affected_poi_id": affected.poi_id,
                "force_replace": True,
                "replacement_category": "咖啡馆",
                "prefer_tags": ["咖啡", "安静"],
            },
            intent=intent,
            user_profile=profile,
        )
    )

    replacement = response.routes[0].changed_stops[0]
    stop = next(stop for stop in response.routes[0].stops if stop.poi_id == replacement.to_poi_id)
    assert stop.category == "cafe" or stop.meal_type == "cafe"


def test_preserve_poi_ids_prevents_user_requested_replacement() -> None:
    route, intent, profile = _route_for_replan(["citywalk", "吃好"])
    preserved = route.stops[1]

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="replace_poi",
            event_label="用户又说这个点保留",
            current_routes=[route],
            event_payload={
                "affected_poi_id": preserved.poi_id,
                "preserve_poi_ids": [preserved.poi_id],
                "force_replace": True,
            },
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert preserved.poi_id in [stop.poi_id for stop in updated.stops]
    assert not updated.changed_stops


def test_mild_queue_spike_warns_without_replacement() -> None:
    route, intent, profile = _route_for_replan(["少排队"])
    affected = route.stops[1]

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="queue_spike",
            event_label="排队变长但还能接受",
            current_routes=[route],
            event_payload={"affected_poi_id": affected.poi_id, "queue_minutes": 25},
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert affected.poi_id in [stop.poi_id for stop in updated.stops]
    assert not updated.changed_stops
    assert any("实时排队约 25 分钟" in warning for warning in updated.live_warnings)
    assert "无需替换" in (updated.replan_reason or "")


def test_warning_only_never_replaces_available_poi() -> None:
    route, intent, profile = _route_for_replan(["citywalk"])
    affected = route.stops[1]

    response = ReplanService().replan(
        ReplanRequest(
            session_id="session_demo",
            selected_route_id=route.route_id,
            event_type="replace_poi",
            event_label="只提醒不替换",
            current_routes=[route],
            event_payload={
                "affected_poi_id": affected.poi_id,
                "force_replace": True,
                "warning_only": True,
                "queue_minutes": 30,
            },
            intent=intent,
            user_profile=profile,
        )
    )

    updated = response.routes[0]
    assert affected.poi_id in [stop.poi_id for stop in updated.stops]
    assert not updated.changed_stops


def test_mock_live_queue_is_stable_within_cache_window_and_category_sensitive() -> None:
    provider = MockMapProvider()

    restaurant = provider.get_place_status(
        "poi_restaurant",
        {"base_queue_minutes": 10, "category": "restaurant", "seed": "s1"},
    )
    same_restaurant = provider.get_place_status(
        "poi_restaurant",
        {"base_queue_minutes": 10, "category": "restaurant", "seed": "s1"},
    )
    cafe = provider.get_place_status(
        "poi_cafe",
        {"base_queue_minutes": 10, "category": "cafe", "seed": "s1"},
    )

    assert restaurant.queue_minutes == same_restaurant.queue_minutes
    assert restaurant.valid_until
    assert cafe.queue_minutes is not None
    assert restaurant.queue_minutes is not None
