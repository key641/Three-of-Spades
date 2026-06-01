from app.services.amap_service import AmapService, GeoPoint
from app.services.mock_route_map_service import MockRouteMapService


def test_mock_route_leg_contains_map_ready_fields_without_key() -> None:
    service = AmapService(api_key="")

    leg = service.route_leg(
        origin=GeoPoint(lat=31.2304, lng=121.4737),
        destination=GeoPoint(lat=31.2397, lng=121.4998),
        mode="walk",
    )

    assert leg.source == "mock_map"
    assert leg.mode == "walk"
    assert leg.distance_meters > 0
    assert leg.duration_minutes > 0
    assert leg.polyline
    assert leg.steps


def test_legacy_fallback_route_leg_can_still_be_forced() -> None:
    service = AmapService(api_key="", route_provider="fallback")

    leg = service.route_leg(
        origin=GeoPoint(lat=31.2304, lng=121.4737),
        destination=GeoPoint(lat=31.2397, lng=121.4998),
        mode="walk",
    )

    assert leg.source == "fallback"
    assert leg.polyline == "121.4737,31.2304;121.4998,31.2397"


def test_mock_metro_route_contains_line_station_and_stop_count() -> None:
    service = MockRouteMapService()

    leg = service.route_leg(
        origin=GeoPoint(lat=31.2304, lng=121.4737),
        destination=GeoPoint(lat=31.2387, lng=121.5026),
        mode="metro",
    )

    instructions = " ".join(step.instruction for step in leg.steps)
    assert leg.source == "mock_map"
    assert leg.mode == "metro"
    assert "地铁2号线" in instructions
    assert "人民广场站" in instructions
    assert "陆家嘴站" in instructions
    assert "站" in instructions
    assert "分钟" in instructions
    assert "公里" in instructions or "米" in instructions


def test_mock_bus_route_contains_bus_line() -> None:
    service = MockRouteMapService()

    leg = service.route_leg(
        origin=GeoPoint(lat=31.1950, lng=121.4376),
        destination=GeoPoint(lat=31.2304, lng=121.4737),
        mode="bus",
    )

    instructions = " ".join(step.instruction for step in leg.steps)
    assert leg.source == "mock_map"
    assert leg.mode == "bus"
    assert "公交49路" in instructions


def test_mock_taxi_peak_time_is_slower_than_normal_time() -> None:
    service = MockRouteMapService()
    origin = GeoPoint(lat=39.9072, lng=116.3740)
    destination = GeoPoint(lat=39.9095, lng=116.4618)

    normal = service.route_leg(origin, destination, mode="taxi", departure_time="14:00")
    peak = service.route_leg(origin, destination, mode="taxi", departure_time="18:00")

    assert peak.duration_minutes > normal.duration_minutes


def test_mock_route_is_stable_for_same_input() -> None:
    service = MockRouteMapService()
    origin = GeoPoint(lat=39.9072, lng=116.3740)
    destination = GeoPoint(lat=39.9095, lng=116.4618)

    first = service.route_leg(origin, destination, mode="metro")
    second = service.route_leg(origin, destination, mode="metro")

    assert first == second
