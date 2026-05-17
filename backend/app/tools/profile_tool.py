from app.schemas.intent import Intent
from app.schemas.user import StrategyWeights, UserProfile
from app.services.profile_service import ProfileService


service = ProfileService()


def get_user_profile(user_id: str) -> UserProfile:
    return service.get_profile(user_id)


def build_strategy_weights(intent: Intent, profile: UserProfile) -> StrategyWeights:
    return service.build_strategy_weights(intent, profile)

