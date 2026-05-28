import json
from pathlib import Path
from typing import Any

from app.agent.intent_enhancer import normalize_avoid_tags, normalize_preferences
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent
from app.schemas.user import StrategyWeights, UserProfile


class ProfileService:
    """A-owned module: profile tags, preference weights, and feedback updates."""

    BUDGET_BY_LEVEL = {
        "low": 100,
        "mid": 300,
        "high": 600,
    }

    DEFAULT_WEIGHTS = {"quality": 0.3, "queue": 0.25, "distance": 0.2, "budget": 0.15, "preference": 0.1}

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[3] / "data" / "seed" / "user_profiles.json"
        self._seed_profiles = self._load_seed_profiles()

    def get_profile(self, user_id: str, request: ChatRequest | None = None) -> UserProfile:
        if request and (request.preferences or request.avoid_tags or request.preference_weights):
            preferences = normalize_preferences(request.preferences)
            return UserProfile(
                user_id=user_id,
                tags=preferences,
                preferences=preferences,
                avoid_tags=normalize_avoid_tags(request.avoid_tags),
                preference_weights=request.preference_weights or self.DEFAULT_WEIGHTS,
            )

        seed_profile = self._profile_from_seed(user_id)
        if seed_profile is not None:
            return seed_profile

        tags = ["少排队", "吃好", "citywalk"]
        return UserProfile(
            user_id=user_id,
            tags=tags,
            preferences=tags,
            avoid_tags=[],
            preference_weights=self.DEFAULT_WEIGHTS,
        )

    def build_strategy_weights(self, intent: Intent, profile: UserProfile) -> StrategyWeights:
        weights = StrategyWeights.model_validate(profile.preference_weights or {})
        if "少排队" in intent.preferences:
            weights.queue = max(weights.queue, 0.3)
        if "更省钱" in intent.preferences:
            weights.budget = max(weights.budget, 0.3)
        if "少走路" in intent.preferences:
            weights.distance = max(weights.distance, 0.25)
        return weights

    def merge_request_into_intent(self, intent: Intent, request: ChatRequest) -> Intent:
        data = intent.model_dump()
        if request.city and not intent.city_from_message:
            data["city"] = request.city

        scenario = request.scenario or (request.scenarios[0] if request.scenarios else None)
        if scenario:
            data["scenario"] = scenario

        data["preferences"] = normalize_preferences([*intent.preferences, *request.preferences])
        data["avoid_tags"] = normalize_avoid_tags([*intent.avoid_tags, *request.avoid_tags])

        budget = self.BUDGET_BY_LEVEL.get((request.budget_level or "").lower())
        if budget is not None:
            data["budget_per_person"] = budget

        return Intent.model_validate(data)

    def update_from_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        # TODO(A): parse feedback and persist profile tag updates.
        return FeedbackResponse(
            user_id=request.user_id,
            updated_tags=["少排队", "少走路"],
            message="已记录反馈，后续会优先推荐少排队、少走路的路线。",
        )

    def _unique(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _load_seed_profiles(self) -> dict[str, dict[str, Any]]:
        try:
            with self.data_path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        users = payload.get("users", [])
        if not isinstance(users, list):
            return {}
        return {str(user.get("user_id")): user for user in users if isinstance(user, dict) and user.get("user_id")}

    def _profile_from_seed(self, user_id: str) -> UserProfile | None:
        raw = self._seed_profiles.get(user_id)
        if raw is None:
            return None

        soft_preferences = (
            raw.get("current_trip", {})
            .get("soft_preferences", {})
        )
        preferences = normalize_preferences(self._as_string_list(soft_preferences.get("prefer_tags")))
        avoid_tags = normalize_avoid_tags(self._as_string_list(soft_preferences.get("avoid_tags")))
        return UserProfile(
            user_id=user_id,
            tags=preferences,
            preferences=preferences,
            avoid_tags=avoid_tags,
            preference_weights=self._weights_from_seed(raw),
        )

    def _weights_from_seed(self, raw: dict[str, Any]) -> dict[str, float]:
        preference_profile = raw.get("preference_profile", {})
        budget_sensitivity = self._to_float(preference_profile.get("budget_sensitivity"), 0.5)
        walking_tolerance = self._to_float(preference_profile.get("walking_tolerance"), 0.5)
        crowd_tolerance = self._to_float(preference_profile.get("crowd_tolerance"), 0.5)
        novelty_preference = self._to_float(preference_profile.get("novelty_preference"), 0.5)
        comfort_preference = self._to_float(preference_profile.get("comfort_preference"), 0.5)

        weights = {
            "quality": 0.25 + comfort_preference * 0.1,
            "queue": 0.15 + (1 - crowd_tolerance) * 0.2,
            "distance": 0.12 + (1 - walking_tolerance) * 0.18,
            "budget": 0.1 + budget_sensitivity * 0.2,
            "preference": 0.08 + novelty_preference * 0.12,
        }
        total = sum(weights.values()) or 1
        return {key: round(value / total, 3) for key, value in weights.items()}

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]

    def _to_float(self, value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
