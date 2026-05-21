from app.schemas.intent import Intent
from app.schemas.user import UserProfile
from app.services.poi_service import POIService


def test_search_loads_pois_from_json() -> None:
    pois = POIService().search(Intent(city="上海"))

    assert pois
    assert all(poi.city == "上海" for poi in pois)


def test_search_returns_enriched_poi_fields() -> None:
    poi = POIService().search(Intent(city="上海"))[0]

    assert poi.district
    assert poi.address
    assert poi.meal_type
    assert poi.cover_image_url
    assert "example.com/mock" not in poi.cover_image_url
    assert poi.last_entry_time
    assert poi.walking_intensity in {"low", "medium", "high"}
    assert poi.highlight_text
    assert poi.highlight_text_tags
    assert poi.primary_category
    assert poi.route_roles
    assert poi.secondary_categories is not None
    assert poi.experience_tags is not None


def test_budget_keeps_expensive_pois_out_of_front_results() -> None:
    pois = POIService().search(Intent(city="上海", budget_per_person=50), limit=10)

    assert pois
    assert all(poi.avg_price <= 50 for poi in pois[:5])


def test_low_queue_preference_prioritizes_short_queues() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["少排队"]), limit=5)

    assert pois
    assert max(poi.queue_minutes for poi in pois) <= 20


def test_food_preference_prioritizes_restaurants() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["吃好"]), limit=5)

    assert pois
    assert any(poi.category == "restaurant" or poi.meal_type in {"local_food", "fine_dining"} for poi in pois[:3])


def test_coffee_preference_prioritizes_cafes() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["咖啡"]), limit=5)

    assert pois
    assert all(poi.category == "cafe" or poi.meal_type == "cafe" for poi in pois)


def test_low_walking_preference_prioritizes_low_walking_intensity() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["少走路"]), limit=5)

    assert pois
    assert sum(1 for poi in pois if poi.walking_intensity == "low") >= 4


def test_indoor_rainy_preference_prioritizes_indoor_or_rainy_pois() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["室内", "雨天"]), limit=5)

    assert pois
    assert all(poi.indoor or poi.rainy_day_score >= 0.7 for poi in pois)


def test_evening_start_prioritizes_available_or_night_friendly_pois() -> None:
    pois = POIService().search(Intent(city="上海", start_time="20:00"), limit=5)

    assert pois
    assert all(poi.last_entry_time >= "20:00" or poi.night_activity >= 0.7 for poi in pois)


def test_avoid_tags_excludes_matching_pois() -> None:
    pois = POIService().search(Intent(city="上海", avoid_tags=["人流密集"]), limit=20)

    assert pois
    assert all("人流密集" not in poi.tags for poi in pois)


def test_start_location_prioritizes_nearby_pois() -> None:
    pois = POIService().search(
        Intent(city="上海", start_location_name="上海科技馆", start_lat=31.2243, start_lng=121.5441),
        limit=5,
    )

    assert pois
    assert any(poi.id in {"poi_001", "poi_003"} for poi in pois[:3])


def test_user_profile_affects_ranking() -> None:
    service = POIService()
    plain = service.search(Intent(city="上海"), limit=10)
    profiled = service.search(
        Intent(city="上海"),
        user_profile=UserProfile(
            user_id="user_demo",
            tags=["少排队", "吃好", "citywalk"],
            preference_weights={"quality": 0.3, "queue": 0.25, "distance": 0.2, "budget": 0.15, "preference": 0.1},
        ),
        limit=10,
    )

    assert profiled
    assert [poi.id for poi in plain] != [poi.id for poi in profiled]
