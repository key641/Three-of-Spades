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
