import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from app.services.amap_service import AmapService, GeoPoint


def test_fallback_route_leg_contains_map_ready_fields_without_key() -> None:
    service = AmapService(api_key="")

    leg = service.route_leg(
        origin=GeoPoint(lat=31.2304, lng=121.4737),
        destination=GeoPoint(lat=31.2397, lng=121.4998),
        mode="walk",
    )

    assert leg.source == "fallback"
    assert leg.mode == "walk"
    assert leg.distance_meters > 0
    assert leg.duration_minutes > 0
    assert leg.polyline == "121.4737,31.2304;121.4998,31.2397"
    assert leg.steps == []


def test_route_leg_caches_same_origin_destination_and_mode() -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "status": "1",
        "route": {"paths": [{"distance": "1200", "duration": "600", "steps": [{"distance": "1200", "duration": "600", "polyline": "a;b"}]}]},
    }
    client = Mock()
    client.get.return_value = response
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)

    with patch("app.services.amap_service.httpx.Client", return_value=client):
        service = AmapService(api_key="test-key")
        origin = GeoPoint(lat=31.2304, lng=121.4737)
        destination = GeoPoint(lat=31.2397, lng=121.4998)

        first = service.route_leg(origin, destination, mode="walk")
        second = service.route_leg(origin, destination, mode="walk")

    assert first == second
    assert first.source == "amap"
    assert client.get.call_count == 1


def test_route_leg_shares_inflight_request_for_same_origin_destination_and_mode() -> None:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "status": "1",
        "route": {"paths": [{"distance": "1200", "duration": "600", "steps": [{"distance": "1200", "duration": "600", "polyline": "a;b"}]}]},
    }
    get_started = threading.Event()
    release_get = threading.Event()
    client = Mock()

    def slow_get(*args, **kwargs):
        get_started.set()
        release_get.wait(timeout=2)
        return response

    client.get.side_effect = slow_get
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)

    with patch("app.services.amap_service.httpx.Client", return_value=client):
        service = AmapService(api_key="test-key")
        origin = GeoPoint(lat=31.2304, lng=121.4737)
        destination = GeoPoint(lat=31.2397, lng=121.4998)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(service.route_leg, origin, destination, "walk")
            assert get_started.wait(timeout=1)
            second_future = pool.submit(service.route_leg, origin, destination, "walk")
            time.sleep(0.05)
            assert client.get.call_count == 1
            release_get.set()

            first = first_future.result(timeout=1)
            second = second_future.result(timeout=1)

    assert first == second
    assert first.source == "amap"
    assert client.get.call_count == 1
