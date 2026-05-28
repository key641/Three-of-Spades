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
