import json
from pathlib import Path

from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.schemas.user import UserProfile
from app.services.fine_rank_service import FineRankService
from app.services.poi_service import POIService
from app.services.route_service import RouteService


def test_fine_rank_model_artifacts_exist_and_have_metadata() -> None:
    root = Path(__file__).resolve().parents[3]
    model_dir = root / "data" / "models" / "fine_rank"
    metadata = json.loads((model_dir / "model_metadata.json").read_text(encoding="utf-8"))
    schema = json.loads((model_dir / "feature_schema.json").read_text(encoding="utf-8"))

    assert (model_dir / "click_model.joblib").exists()
    assert (model_dir / "like_model.joblib").exists()
    assert (model_dir / "skip_model.joblib").exists()
    assert metadata["sample_count"] == 16000
    assert metadata["model_type"] == "DictVectorizer+LogisticRegression"
    assert set(metadata["label_positive_rates"]) == {"click", "like", "skip"}
    assert schema["feature_schema_version"] == metadata["feature_schema_version"]


def test_fine_rank_probabilities_are_bounded() -> None:
    service = FineRankService()
    poi_service = POIService()
    pois = poi_service.all_pois("上海")
    result = service.score(pois[0], Intent(city="上海"), UserProfile(user_id="u"), poi_universe=pois)

    assert 0 <= result.p_click <= 1
    assert 0 <= result.p_like <= 1
    assert 0 <= result.p_skip <= 1


def test_fine_rank_prioritizes_profile_category_preference() -> None:
    service = FineRankService()
    pois = POIService().all_pois("上海")
    museum = next(poi for poi in pois if poi.category == "museum")
    restaurant = next(poi for poi in pois if poi.category == "restaurant")
    profile = UserProfile(
        user_id="museum_user",
        tags=["展览"],
        preferences=["展览"],
        category_preferences={"museum": 1.0, "restaurant": 0.0},
    )
    intent = Intent(city="上海", preferences=["展览"])

    museum_score = service.score(museum, intent, profile, objective="balanced", poi_universe=pois)
    restaurant_score = service.score(restaurant, intent, profile, objective="balanced", poi_universe=pois)

    assert museum_score.poi_relevance_score > restaurant_score.poi_relevance_score


def test_fine_rank_high_price_raises_skip_for_budget_sensitive_user() -> None:
    service = FineRankService()
    pois = POIService().all_pois("上海")
    cheap = next(poi for poi in pois if poi.avg_price <= 50)
    expensive = next(poi for poi in pois if poi.avg_price >= 180)
    profile = UserProfile(user_id="budget_user", budget_sensitivity=0.9)
    intent = Intent(city="上海", budget_per_person=60)

    cheap_result = service.score(cheap, intent, profile, poi_universe=pois)
    expensive_result = service.score(expensive, intent, profile, poi_universe=pois)

    assert expensive_result.p_skip > cheap_result.p_skip


def test_fine_rank_high_walking_raises_skip_for_low_walking_user() -> None:
    service = FineRankService()
    pois = POIService().all_pois("上海")
    low = next(poi for poi in pois if poi.walking_intensity == "low")
    high = next(poi for poi in pois if poi.walking_intensity == "high")
    profile = UserProfile(user_id="walking_user", walking_tolerance=0.1, tags=["少走路"], preferences=["少走路"])
    intent = Intent(city="上海", preferences=["少走路"])

    low_result = service.score(low, intent, profile, objective="low_walking", poi_universe=pois)
    high_result = service.score(high, intent, profile, objective="low_walking", poi_universe=pois)

    assert high_result.p_skip > low_result.p_skip


def test_fine_rank_disliked_poi_is_penalized() -> None:
    service = FineRankService()
    pois = POIService().all_pois("上海")
    poi = pois[0]
    neutral = UserProfile(user_id="neutral")
    disliked = UserProfile(user_id="disliked", disliked_poi_ids=[poi.id])
    intent = Intent(city="上海")

    neutral_result = service.score(poi, intent, neutral, poi_universe=pois)
    disliked_result = service.score(poi, intent, disliked, poi_universe=pois)

    assert disliked_result.p_skip > neutral_result.p_skip
    assert disliked_result.poi_relevance_score < neutral_result.poi_relevance_score


def test_fine_rank_fallback_works_without_model_files(tmp_path: Path) -> None:
    service = FineRankService(model_dir=tmp_path)
    pois = POIService().all_pois("上海")
    result = service.score(pois[0], Intent(city="上海"), UserProfile(user_id="u"), poi_universe=pois)

    assert 0 <= result.p_click <= 1
    assert 0 <= result.p_like <= 1
    assert 0 <= result.p_skip <= 1


def test_route_service_poi_score_uses_fine_rank_relevance() -> None:
    route_service = RouteService()
    pois = POIService().all_pois("上海")
    poi = pois[0]
    request_without_score = RoutePlanRequest(intent=Intent(city="上海"), user_profile=UserProfile(user_id="u"), candidate_pois=[poi])
    request_with_score = RoutePlanRequest(
        intent=Intent(city="上海"),
        user_profile=UserProfile(user_id="u"),
        candidate_pois=[poi],
        poi_relevance_scores={poi.id: 1.0},
    )

    base_score = route_service._poi_score(poi, "balanced", request_without_score, None, None)
    boosted_score = route_service._poi_score(poi, "balanced", request_with_score, None, None)

    assert boosted_score > base_score
