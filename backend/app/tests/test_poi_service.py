import json
import math
from collections import Counter
from pathlib import Path

from app.schemas.intent import Intent
from app.schemas.user import UserProfile
from app.services.coarse_rank_service import CoarseRankService
from app.services.poi_service import POIService
from app.services.strategy_service import StrategyService


KEY_CITIES = {"上海", "北京"}
EXPECTED_CATEGORY_COUNTS = {
    "restaurant": 140,
    "cafe": 120,
    "market": 80,
    "shopping": 80,
    "boutique": 40,
    "bookstore": 40,
    "lifestyle_store": 40,
    "toy_collectible": 40,
    "sports_outdoor": 40,
    "beauty_retail": 40,
    "design_store": 40,
    "landmark": 80,
    "museum": 70,
    "gallery": 70,
    "park": 70,
    "night_view": 70,
    "theater": 60,
}


def test_search_loads_pois_from_json() -> None:
    pois = POIService().search(Intent(city="上海"))

    assert pois
    assert all(poi.city == "上海" for poi in pois)


def test_search_returns_enriched_poi_fields() -> None:
    poi = POIService().search(Intent(city="上海"))[0]

    assert poi.district
    assert poi.business_area
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


def test_rank_score_wrapper_delegates_to_coarse_rank_service() -> None:
    service = POIService()
    candidate = next(candidate for candidate in service._candidates if candidate.poi.city == "上海")
    intent = Intent(city="上海", preferences=["citywalk"])
    profile = UserProfile(user_id="u", tags=["拍照"], preferences=[], preference_weights={})

    assert service._rank_score(candidate, intent, profile) == service.coarse_rank_service.score(candidate, intent, profile, [])


def test_coarse_rank_result_contains_feature_breakdown() -> None:
    service = POIService()
    ranker = CoarseRankService(service.strategy_service)
    candidates = [candidate for candidate in service._candidates if candidate.poi.city == "上海"][:5]

    result = ranker.rank_with_features(candidates, Intent(city="上海"), limit=1)[0]

    assert result.candidate in candidates
    assert result.score > 0
    assert {
        "preference_match",
        "budget_fit",
        "queue_crowd",
        "quality",
        "distance_fit",
        "time_fit",
        "avoid_risk",
        "profile_fit",
        "scenario_fit",
        "strategy_tag_match",
    } <= set(result.features)


def test_coarse_rank_preference_match_prioritizes_cafe() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    cafe = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.category == "cafe")
    museum = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.category == "museum")
    intent = Intent(city="上海", preferences=["咖啡"])

    assert ranker.score(cafe, intent, None, []) > ranker.score(museum, intent, None, [])


def test_coarse_rank_budget_fit_prefers_budget_friendly_poi() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    cheap = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.avg_price <= 50)
    expensive = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.avg_price >= 180)
    intent = Intent(city="上海", budget_per_person=60)

    assert ranker.features(cheap, intent, None)["budget_fit"] > ranker.features(expensive, intent, None)["budget_fit"]


def test_coarse_rank_queue_fit_prefers_short_queue() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    short_queue = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.queue_minutes <= 5)
    long_queue = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.queue_minutes >= 45)
    intent = Intent(city="上海", preferences=["少排队"])

    assert ranker.features(short_queue, intent, None)["queue_crowd"] > ranker.features(long_queue, intent, None)["queue_crowd"]


def test_coarse_rank_distance_fit_prefers_nearby_poi() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    near = next(candidate for candidate in service._candidates if candidate.poi.city == "上海")
    far = next(
        candidate
        for candidate in service._candidates
        if candidate.poi.city == "上海" and math.hypot(candidate.poi.lat - near.poi.lat, candidate.poi.lng - near.poi.lng) > 0.04
    )
    intent = Intent(city="上海", start_lat=near.poi.lat, start_lng=near.poi.lng)

    assert ranker.features(near, intent, None)["distance_fit"] > ranker.features(far, intent, None)["distance_fit"]


def test_coarse_rank_time_fit_penalizes_after_last_entry() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    candidate = next(candidate for candidate in service._candidates if candidate.poi.city == "上海")
    open_poi = candidate.poi.model_copy(update={"open_time": "09:00", "close_time": "23:00", "last_entry_time": "22:30"})
    closed_poi = candidate.poi.model_copy(update={"open_time": "09:00", "close_time": "18:00", "last_entry_time": "17:30"})
    open_candidate = candidate.__class__(poi=open_poi, search_text=candidate.search_text, risk_text=candidate.risk_text)
    closed_candidate = candidate.__class__(poi=closed_poi, search_text=candidate.search_text, risk_text=candidate.risk_text)
    intent = Intent(city="上海", start_time="20:00")

    assert ranker.features(open_candidate, intent, None)["time_fit"] > ranker.features(closed_candidate, intent, None)["time_fit"]


def test_coarse_rank_avoid_risk_penalizes_risky_text() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    candidate = next(candidate for candidate in service._candidates if candidate.poi.city == "上海")
    risky = candidate.__class__(poi=candidate.poi, search_text=candidate.search_text, risk_text="人流密集 排队久")
    intent = Intent(city="上海", avoid_tags=["人流密集"])

    assert ranker.score(candidate, intent, None, []) > ranker.score(risky, intent, None, [])


def test_coarse_rank_profile_fit_supports_category_preferences() -> None:
    service = POIService()
    ranker = service.coarse_rank_service
    museum = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.category == "museum")
    restaurant = next(candidate for candidate in service._candidates if candidate.poi.city == "上海" and candidate.poi.category == "restaurant")
    intent = Intent(city="上海")
    museum_profile = UserProfile(user_id="museum_u", category_preferences={"museum": 1.0, "restaurant": 0.0})
    restaurant_profile = UserProfile(user_id="food_u", category_preferences={"museum": 0.0, "restaurant": 1.0})

    assert ranker.score(museum, intent, museum_profile, []) > ranker.score(restaurant, intent, museum_profile, [])
    assert ranker.score(restaurant, intent, restaurant_profile, []) > ranker.score(museum, intent, restaurant_profile, [])


def test_coarse_rank_top_sixty_keeps_category_diversity() -> None:
    service = POIService()
    intent = Intent(city="上海", preferences=["咖啡", "吃好"])
    city_candidates = [candidate for candidate in service._candidates if candidate.poi.city == "上海"]
    recalled = service.recall_service.recall(intent, city_candidates, target_pool_size=240)
    ranked = service.coarse_rank_service.rank(recalled, intent, limit=60)

    assert len(ranked) == 60
    assert len({candidate.poi.category for candidate in ranked}) >= 4
    assert max(Counter(candidate.poi.category for candidate in ranked).values()) < 60


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
        assert raw["district"]
        assert raw["business_area"]
        assert raw["district"] == location["district"]
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


def test_seed_poi_names_are_realistic_and_area_tagged() -> None:
    payload = json.loads((Path(__file__).resolve().parents[3] / "data" / "seed" / "pois.json").read_text(encoding="utf-8"))
    bad_tokens = ["推荐路", "示范路", "慢游点"]

    for raw in payload["pois"]:
        assert not raw["name"][-1].isdigit()
        assert not any(token in raw["name"] for token in bad_tokens)
        assert not any(token in raw["location"]["address"] for token in bad_tokens)


def test_region_terms_soft_prioritize_district_and_business_area() -> None:
    district_results = POIService().search(Intent(city="上海", preferences=["徐汇区", "citywalk"]), limit=8)
    area_results = POIService().search(Intent(city="上海", preferences=["武康路", "逛店"]), limit=8)

    assert sum(1 for poi in district_results[:5] if poi.district == "徐汇区") >= 3
    assert any("武康路" in poi.business_area for poi in area_results[:5])


def test_key_city_searches_do_not_return_empty_results() -> None:
    service = POIService()

    for city in ["上海", "北京"]:
        pois = service.search(Intent(city=city))

        assert len(pois) == 60
        assert all(poi.city == city for poi in pois)


def test_default_search_returns_sixty_pois() -> None:
    service = POIService()

    assert len(service.search(Intent(city="上海"))) == 60
    assert len(service.search(Intent(city="北京"))) == 60


def test_strong_filters_still_fill_to_sixty_when_possible() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["少排队", "拍照"], avoid_tags=["人流密集"]))

    assert len(pois) == 60
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


def test_unknown_city_returns_empty_candidates_instead_of_mock_fallback() -> None:
    pois = POIService().search(Intent(city="哈尔滨"), limit=12)

    assert pois == []


def test_unknown_city_region_returns_empty_candidates() -> None:
    pois = POIService().search(Intent(city="哈尔滨", target_district="道里区"), limit=12)

    assert pois == []


def test_city_region_without_data_returns_empty_candidates() -> None:
    pois = POIService().search(Intent(city="上海", target_district="不存在区"), limit=12)

    assert pois == []


def test_interaction_events_cover_users_and_pois() -> None:
    root = Path(__file__).resolve().parents[3]
    events = json.loads((root / "data" / "seed" / "interaction_events.json").read_text(encoding="utf-8"))
    pois = json.loads((root / "data" / "seed" / "pois.json").read_text(encoding="utf-8"))["pois"]
    users = json.loads((root / "data" / "seed" / "user_profiles.json").read_text(encoding="utf-8"))["users"]
    poi_ids = {poi["poi_id"] for poi in pois}
    user_ids = {user["user_id"] for user in users}
    by_user = Counter(event["user_id"] for event in events)
    by_poi = Counter(event["poi_id"] for event in events)
    positive = sum(1 for event in events if event["event_value"] > 0)

    assert len(events) == 16000
    assert set(by_user) == user_ids
    assert set(by_poi) == poi_ids
    assert all(160 <= count <= 240 for count in by_user.values())
    assert min(by_poi.values()) >= 4
    assert 0.55 <= positive / len(events) <= 0.75


def test_recall_model_artifacts_exist_and_have_expected_shape() -> None:
    root = Path(__file__).resolve().parents[3]
    user_embeddings = json.loads((root / "data" / "models" / "two_tower" / "user_embeddings.json").read_text(encoding="utf-8"))
    poi_embeddings = json.loads((root / "data" / "models" / "two_tower" / "poi_embeddings.json").read_text(encoding="utf-8"))
    item_similarity = json.loads((root / "data" / "models" / "cf" / "item_similarity.json").read_text(encoding="utf-8"))
    first_user_vector = next(iter(user_embeddings["embeddings"].values()))
    first_poi_vector = next(iter(poi_embeddings["embeddings"].values()))

    assert user_embeddings["dimension"] == 64
    assert poi_embeddings["dimension"] == 64
    assert len(first_user_vector) == 64
    assert len(first_poi_vector) == 64
    assert len(user_embeddings["embeddings"]) == 80
    expected_poi_count = len(json.loads((root / "data" / "seed" / "pois.json").read_text(encoding="utf-8"))["pois"])
    assert len(poi_embeddings["embeddings"]) == expected_poi_count
    assert len(item_similarity["items"]) == expected_poi_count


def test_default_recall_results_are_not_limited_to_two_categories() -> None:
    pois = POIService().search(Intent(city="上海"), limit=40)

    assert len({poi.category for poi in pois}) >= 4
    assert any("main_activity" in poi.route_roles for poi in pois)
    assert any("meal" in poi.route_roles or "coffee_break" in poi.route_roles for poi in pois)
    assert any("photo_stop" in poi.route_roles for poi in pois)


def test_shopping_recall_includes_fine_grained_store_categories() -> None:
    pois = POIService().search(Intent(city="上海", preferences=["武康路", "逛店", "书店", "买手店"]), limit=20)
    store_categories = {"boutique", "bookstore", "lifestyle_store", "toy_collectible", "sports_outdoor", "beauty_retail", "design_store"}

    assert any(poi.category in store_categories for poi in pois[:10])
    assert any("武康路" in poi.business_area for poi in pois[:10])
