from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.schemas.intent import Intent
from app.schemas.user import StrategyWeights, UserProfile


class ProfileService:
    """A-owned module: profile tags, preference weights, and feedback updates."""

    def get_profile(self, user_id: str) -> UserProfile:
        return UserProfile(
            user_id=user_id,
            tags=["少排队", "吃好", "citywalk"],
            preference_weights={"quality": 0.3, "queue": 0.25, "distance": 0.2, "budget": 0.15, "preference": 0.1},
        )

    def build_strategy_weights(self, intent: Intent, profile: UserProfile) -> StrategyWeights:
        weights = StrategyWeights()
        if "少排队" in intent.preferences:
            weights.queue = 0.3
        if "更省钱" in intent.preferences:
            weights.budget = 0.3
        if "少走路" in intent.preferences:
            weights.distance = 0.25
        return weights

    def update_from_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        # TODO(A): parse feedback and persist profile tag updates.
        return FeedbackResponse(
            user_id=request.user_id,
            updated_tags=["少排队", "少走路"],
            message="已记录反馈，后续会优先推荐少排队、少走路的路线。",
        )

