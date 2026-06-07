from app.schemas.intent import Intent
from app.schemas.user import StrategyWeights, UserProfile
from app.services.strategy_service import StrategyService


def test_photo_intensity_changes_weight_smoothly() -> None:
    service = StrategyService()
    profile = UserProfile(user_id="u", tags=[], preferences=[], preference_weights=StrategyWeights().model_dump())

    weak_tags = service.infer_tags("可以拍照", Intent(preferences=["拍照"]), profile)
    strong_tags = service.infer_tags("饭店拍照必须好看，吃美食", Intent(preferences=["拍照", "吃好"]), profile)
    weak = service.build_weights(StrategyWeights(), weak_tags)
    strong = service.build_weights(StrategyWeights(), strong_tags)

    assert weak.preference > StrategyWeights().preference
    assert strong.preference > weak.preference
    assert any(tag.tag == "photo_food" and tag.intensity >= 0.85 for tag in strong_tags)


def test_low_queue_profile_does_not_create_objective_affinity() -> None:
    service = StrategyService()
    profile = UserProfile(user_id="u", tags=["少排队"], preferences=["少排队"], preference_weights=StrategyWeights().model_dump())
    tags = service.infer_tags("我想看自然风景", Intent(preferences=["自然风景"]), profile)
    scores = service.objective_scores(tags, profile, {"nature_relax": 10, "balanced": 10})

    assert "low_queue" not in scores
    assert scores["nature_relax"] > scores["balanced"]


def test_chongqing_half_day_tags_have_distinct_intensity() -> None:
    service = StrategyService()
    profile = UserProfile(user_id="u", tags=[], preferences=[], preference_weights=StrategyWeights().model_dump())
    message = "我打算下午和朋友在重庆半日游，不希望一直在室外，能够打卡地标景点还能出片，吃点重庆特色美食。"
    intent = Intent(city="重庆", duration_hours=4, preferences=["室内", "拍照", "吃好", "citywalk"])

    tags = {tag.tag: tag for tag in service.infer_tags(message, intent, profile)}

    assert tags["indoor_rainy"].intensity >= tags["photo"].intensity
    assert tags["photo"].intensity > tags["food_first"].intensity
    assert tags["photo_food"].intensity < tags["photo"].intensity
    assert len({tag.intensity for tag in tags.values()}) > 1
