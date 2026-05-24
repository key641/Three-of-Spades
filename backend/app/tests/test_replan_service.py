from app.schemas.intent import Intent
from app.schemas.route import ReplanRequest, RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.replan_service import ReplanService
from app.services.route_service import RouteService


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
