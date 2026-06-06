import json
import math
from collections import Counter
from pathlib import Path

from app.schemas.intent import Intent
from app.schemas.user import UserProfile
from app.services.poi_service import POIService
from app.services.strategy_service import StrategyService


KEY_CITIES = {"上海", "北京"}
EXPECTED_CATEGORY_COUNTS = {
    "restaurant": 70,
    "cafe": 60,
    "market": 40,
    "shopping": 40,
    "landmark": 40,
    "museum": 35,
    "gallery": 35,
    "park": 35,
    "night_view": 35,
    "theater": 30,
}


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


def test_saving_money_goal_uses_price_not_text_tag() -> None:
    pois = POIService().search(Intent(city="上海", optimization_goals=["省钱"], budget_per_person=120), limit=8)

    assert pois
    assert sum(1 for poi in pois[:5] if poi.avg_price <= 120 or poi.budget_friendly >= 0.7) >= 4


def test_food_preference_prioritizes_restaurants() -> None:
    pois = POIService().search(Intent(city="上海", interest_tags=["美食"]), limit=5)

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
    assert all(math.hypot((poi.lat - 31.2243) * 111, (poi.lng - 121.5441) * 95) <= 3 for poi in pois[:3])


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


def test_algorithm_profile_dimensions_affect_poi_ranking() -> None:
    service = POIService()
    museum = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.category == "museum")
    restaurant = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.category == "restaurant")
    intent = Intent(city="上海")

    museum_profile = UserProfile(
        user_id="u1",
        category_preferences={"museum": 1.0, "restaurant": 0.0},
        preferred_route_roles=["main_activity"],
        preferred_experience_tags=["展览"],
    )
    restaurant_profile = UserProfile(
        user_id="u2",
        category_preferences={"museum": 0.0, "restaurant": 1.0},
        preferred_route_roles=["meal"],
    )

    assert service._rank_score(museum, intent, museum_profile) > service._rank_score(museum, intent, restaurant_profile)
    assert service._rank_score(restaurant, intent, restaurant_profile) > service._rank_score(restaurant, intent, museum_profile)


def test_seed_data_covers_key_cities_and_scenarios() -> None:
    pois = POIService().all_pois()
    by_city = Counter(poi.city for poi in pois)

    assert set(by_city) == KEY_CITIES
    assert all(by_city[city] == sum(EXPECTED_CATEGORY_COUNTS.values()) for city in KEY_CITIES)
    for city in KEY_CITIES:
        city_pois = [poi for poi in pois if poi.city == city]
        by_category = Counter(poi.category for poi in city_pois)
        assert by_category == EXPECTED_CATEGORY_COUNTS
        assert any(poi.category in {"restaurant", "market"} or poi.meal_type in {"local_food", "light_meal", "fine_dining"} for poi in city_pois)
        assert any(poi.category == "cafe" or poi.meal_type == "cafe" for poi in city_pois)
        assert any(poi.indoor for poi in city_pois)
        assert any(poi.photo_friendly >= 0.7 or "拍照" in poi.tags for poi in city_pois)
        assert any(poi.night_activity >= 0.7 or "night" in poi.suitable_time_slots for poi in city_pois)
        assert any(poi.avg_price <= 80 or poi.budget_friendly >= 0.8 for poi in city_pois)
        assert any(poi.walking_intensity == "low" for poi in city_pois)
        assert any(poi.category == "park" or poi.primary_category == "nature" for poi in city_pois)


def test_seed_data_has_valid_planning_fields() -> None:
    payload = json.loads((Path(__file__).resolve().parents[3] / "data" / "seed" / "pois.json").read_text(encoding="utf-8"))
    ids = {raw["poi_id"] for raw in payload["pois"]}

    for raw in payload["pois"]:
        location = raw["location"]
        visit_info = raw["visit_info"]
        quality = raw["quality"]
        planning = raw["planning_features"]

        assert raw["poi_id"]
        assert location["city"]
        assert -90 <= float(location["lat"]) <= 90
        assert -180 <= float(location["lng"]) <= 180
        assert int(visit_info["price_min"]) <= int(visit_info["price_max"])
        assert 0 <= int(quality["queue_time_min"]) <= 180
        assert 0 <= float(quality["rating"]) <= 5
        assert visit_info["open_time"] < "24:00"
        assert visit_info["close_time"] <= "23:59"
        assert planning["meal_type"]
        assert planning["walking_intensity"] in {"low", "medium", "high"}
        assert all(poi_id in ids for poi_id in planning["nearby_poi_ids"])


def test_key_city_searches_do_not_return_empty_results() -> None:
    service = POIService()

    for city in ["上海", "北京"]:
        pois = service.search(Intent(city=city))

        assert len(pois) == 40
        assert all(poi.city == city for poi in pois)


def test_default_search_returns_forty_pois() -> None:
    service = POIService()

    assert len(service.search(Intent(city="上海"))) == 40
    assert len(service.search(Intent(city="北京"))) == 40


def test_strong_filters_still_fill_to_forty_when_possible() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["少排队", "拍照"], avoid_tags=["人流密集"]))

    assert len(pois) == 40
    assert all(poi.city == "上海" for poi in pois)


def test_common_preference_searches_do_not_return_empty_results() -> None:
    service = POIService()
    preferences = [
        ["少排队"],
        ["吃好"],
        ["咖啡"],
        ["亲子友好"],
        ["室内", "雨天"],
        ["晚上", "夜景"],
        ["安静", "人少"],
    ]

    for terms in preferences:
        pois = service.search(Intent(city="北京", preferences=terms), limit=12)

        assert pois, terms
        assert all(poi.city == "北京" for poi in pois)


def test_low_budget_and_avoid_tags_still_keep_candidates() -> None:
    pois = POIService().search(Intent(city="北京", budget_per_person=50, avoid_tags=["人流密集", "太贵"]), limit=20)

    assert len(pois) >= 12
    assert all("人流密集" not in poi.tags for poi in pois)


def test_photo_food_strategy_prioritizes_photo_friendly_food() -> None:
    service = POIService()
    profile = UserProfile(user_id="u", tags=[], preferences=[], preference_weights={})
    intent = Intent(city="上海", preferences=["拍照", "吃好"])
    tags = StrategyService().infer_tags("饭店拍照必须好看，吃美食", intent, profile)
    pois = service.search(intent, user_profile=profile, strategy_tags=tags, limit=10)

    assert any(poi.category in {"restaurant", "cafe", "market"} and (poi.photo_friendly >= 0.7 or "拍照" in poi.tags) for poi in pois[:5])


def test_nature_strategy_prioritizes_nature_pois() -> None:
    service = POIService()
    profile = UserProfile(user_id="u", tags=[], preferences=[], preference_weights={})
    intent = Intent(city="北京", preferences=["自然风景"])
    tags = StrategyService().infer_tags("想看自然风景，轻松一点", intent, profile)
    pois = service.search(intent, user_profile=profile, strategy_tags=tags, limit=10)

    assert any(poi.category == "park" or poi.primary_category == "nature" for poi in pois[:5])


def test_unknown_city_uses_mock_fallback_candidates() -> None:
    pois = POIService().search(Intent(city="哈尔滨"), limit=12)

    assert len(pois) == 12
    assert all(poi.city == "哈尔滨" for poi in pois)
    assert all(poi.source_provider == "mock_fallback" for poi in pois)
