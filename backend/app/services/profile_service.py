from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent.intent_enhancer import normalize_avoid_tags, normalize_goal_preferences, normalize_interest_preferences, normalize_preferences
from app.agent.tag_taxonomy import legacy_preferences_from_layers
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.schemas.chat import ChatRequest
from app.schemas.intent import Intent
from app.schemas.user import StrategyTag, StrategyWeights, UserProfile
from app.services.strategy_service import StrategyService


class ProfileService:
    """A-owned module: profile tags, preference weights, and feedback updates."""

    BUDGET_BY_LEVEL = {
        "low": 100,
        "mid": 300,
        "high": 600,
    }

    DEFAULT_WEIGHTS = {"quality": 0.3, "queue": 0.25, "distance": 0.2, "budget": 0.15, "preference": 0.1}

    def __init__(self, data_path: Path | None = None, runtime_data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[3] / "data" / "seed" / "user_profiles.json"
        self.runtime_data_path = runtime_data_path or Path(__file__).resolve().parents[3] / "data" / "runtime" / "user_profiles.json"
        self._seed_profiles = self._load_seed_profiles()
        self.strategy_service = StrategyService()

    def get_profile(self, user_id: str, request: ChatRequest | None = None) -> UserProfile:
        if request and self._request_has_profile_fields(request):
            interest_tags = normalize_interest_preferences([*request.preferences, *request.interest_tags])
            optimization_goals = normalize_goal_preferences([*request.preferences, *request.optimization_goals])
            preferences = legacy_preferences_from_layers(interest_tags, optimization_goals)
            profile = UserProfile(
                user_id=user_id,
                tags=preferences,
                preferences=preferences,
                interest_tags=interest_tags,
                optimization_goals=optimization_goals,
                avoid_tags=normalize_avoid_tags(request.avoid_tags),
                preference_weights=request.preference_weights or self.DEFAULT_WEIGHTS,
                budget_sensitivity=self._optional_score(request.budget_sensitivity),
                walking_tolerance=self._optional_score(request.walking_tolerance),
                crowd_tolerance=self._optional_score(request.crowd_tolerance),
                schedule_tightness=self._optional_score(request.schedule_tightness),
                novelty_preference=self._optional_score(request.novelty_preference),
                comfort_preference=self._optional_score(request.comfort_preference),
                category_preferences=self._score_map(request.category_preferences),
                preferred_route_roles=self._unique(request.preferred_route_roles),
                preferred_experience_tags=self._unique(request.preferred_experience_tags),
                preferred_time_slots=self._unique(request.preferred_time_slots),
                preferred_transport_modes=self._unique(request.preferred_transport_modes),
                liked_poi_ids=self._unique(request.liked_poi_ids),
                disliked_poi_ids=self._unique(request.disliked_poi_ids),
                skipped_categories=self._unique(request.skipped_categories),
                common_adjust_actions=self._unique(request.common_adjust_actions),
            )
            self._save_runtime_profile(profile)
            return profile

        runtime_profile = self._profile_from_runtime(user_id)
        if runtime_profile is not None:
            return runtime_profile

        seed_profile = self._profile_from_seed(user_id)
        if seed_profile is not None:
            return seed_profile

        interest_tags = ["美食", "citywalk"]
        optimization_goals = ["少排队"]
        tags = legacy_preferences_from_layers(interest_tags, optimization_goals)
        return UserProfile(
            user_id=user_id,
            tags=tags,
            preferences=tags,
            interest_tags=interest_tags,
            optimization_goals=optimization_goals,
            avoid_tags=[],
            preference_weights=self.DEFAULT_WEIGHTS,
            preferred_route_roles=self._route_roles_from_terms(tags),
            preferred_experience_tags=self._experience_tags_from_terms(tags),
        )

    def get_seed_profile(self, user_id: str) -> UserProfile | None:
        return self._profile_from_seed(user_id)

    def has_seed_profile(self, user_id: str) -> bool:
        return user_id in self._seed_profiles

    def build_strategy_weights(self, intent: Intent, profile: UserProfile, strategy_tags: list[StrategyTag] | None = None) -> StrategyWeights:
        weights = StrategyWeights.model_validate(profile.preference_weights or {})
        weights.budget = max(weights.budget, 0.1 + profile.budget_sensitivity * 0.2)
        weights.distance = max(weights.distance, 0.12 + (1 - profile.walking_tolerance) * 0.18)
        weights.queue = max(weights.queue, 0.15 + (1 - profile.crowd_tolerance) * 0.2)
        weights.preference = max(weights.preference, 0.08 + profile.novelty_preference * 0.12)
        weights.quality = max(weights.quality, 0.25 + profile.comfort_preference * 0.1)
        intent_goals = set(intent.optimization_goals)
        if "少排队" in intent_goals:
            weights.queue = max(weights.queue, 0.3)
        if "省钱" in intent_goals:
            weights.budget = max(weights.budget, 0.3)
        if "少走路" in intent_goals:
            weights.distance = max(weights.distance, 0.25)
        return self.strategy_service.build_weights(weights, strategy_tags or [])

    def update_from_chat(self, profile: UserProfile, intent: Intent, message: str = "") -> UserProfile:
        """Merge explicit chat preferences into the session profile.

        This is the demo-stage profile update hook. It writes to a JSON-backed
        runtime store; a database repository can replace that later without
        changing the orchestrator flow.
        """
        interest_tags = normalize_interest_preferences([*profile.interest_tags, *intent.interest_tags, *profile.preferences, *intent.preferences])
        optimization_goals = normalize_goal_preferences([*profile.optimization_goals, *intent.optimization_goals, *profile.preferences, *intent.preferences])
        preferences = legacy_preferences_from_layers(interest_tags, optimization_goals)
        avoid_tags = normalize_avoid_tags([*profile.avoid_tags, *intent.avoid_tags])
        weights = self.build_strategy_weights(intent, profile).model_dump()
        merged_terms = [*preferences, *avoid_tags]
        updated = UserProfile(
            user_id=profile.user_id,
            tags=preferences,
            preferences=preferences,
            interest_tags=interest_tags,
            optimization_goals=optimization_goals,
            avoid_tags=avoid_tags,
            preference_weights=weights,
            budget_sensitivity=self._updated_budget_sensitivity(profile, merged_terms),
            walking_tolerance=self._updated_walking_tolerance(profile, merged_terms),
            crowd_tolerance=self._updated_crowd_tolerance(profile, merged_terms),
            schedule_tightness=profile.schedule_tightness,
            novelty_preference=self._updated_novelty_preference(profile, merged_terms),
            comfort_preference=self._updated_comfort_preference(profile, merged_terms),
            category_preferences=self._merged_category_preferences(profile, merged_terms),
            preferred_route_roles=self._unique([*profile.preferred_route_roles, *self._route_roles_from_terms(merged_terms)]),
            preferred_experience_tags=self._unique([*profile.preferred_experience_tags, *self._experience_tags_from_terms(merged_terms)]),
            preferred_time_slots=self._unique([*profile.preferred_time_slots, *self._time_slots_from_terms(merged_terms)]),
            preferred_transport_modes=self._unique([*profile.preferred_transport_modes, *self._transport_modes_from_terms(merged_terms)]),
            liked_poi_ids=list(profile.liked_poi_ids),
            disliked_poi_ids=list(profile.disliked_poi_ids),
            skipped_categories=list(profile.skipped_categories),
            common_adjust_actions=list(profile.common_adjust_actions),
        )
        if self._should_persist_long_term_profile(message):
            self._save_runtime_profile(updated)
        return updated

    def merge_request_into_intent(self, intent: Intent, request: ChatRequest) -> Intent:
        data = intent.model_dump()
        if request.city and not intent.city_from_message:
            data["city"] = request.city
        if request.start_location_name and not intent.start_location_name:
            data["start_location_name"] = request.start_location_name
        if request.target_district:
            data["target_district"] = request.target_district
        if request.target_business_area:
            data["target_business_area"] = request.target_business_area
        if request.start_time:
            data["start_time"] = request.start_time
        if request.duration_hours is not None:
            data["duration_hours"] = request.duration_hours
        if request.people_count is not None:
            data["people_count"] = request.people_count
        if not intent.start_location_name and request.start_lat is not None and request.start_lng is not None:
            data["start_lat"] = request.start_lat
            data["start_lng"] = request.start_lng
        elif not intent.start_location_name and request.current_lat is not None and request.current_lng is not None:
            data["start_lat"] = request.current_lat
            data["start_lng"] = request.current_lng

        scenario = request.scenario or (request.scenarios[0] if request.scenarios else None)
        if scenario:
            data["scenario"] = scenario

        interest_tags = normalize_interest_preferences([*intent.interest_tags, *request.interest_tags, *intent.preferences, *request.preferences])
        optimization_goals = normalize_goal_preferences([*intent.optimization_goals, *request.optimization_goals, *intent.preferences, *request.preferences])
        data["interest_tags"] = interest_tags
        data["optimization_goals"] = optimization_goals
        data["preferences"] = normalize_preferences([*intent.preferences, *request.preferences, *interest_tags, *optimization_goals])
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

    def _request_has_profile_fields(self, request: ChatRequest) -> bool:
        return bool(
            request.preferences
            or request.interest_tags
            or request.optimization_goals
            or request.avoid_tags
            or request.preference_weights
            or request.category_preferences
            or request.preferred_route_roles
            or request.preferred_experience_tags
            or request.preferred_time_slots
            or request.preferred_transport_modes
            or request.liked_poi_ids
            or request.disliked_poi_ids
            or request.skipped_categories
            or request.common_adjust_actions
            or request.budget_sensitivity is not None
            or request.walking_tolerance is not None
            or request.crowd_tolerance is not None
            or request.schedule_tightness is not None
            or request.novelty_preference is not None
            or request.comfort_preference is not None
        )

    def _load_runtime_profiles(self) -> dict[str, dict[str, Any]]:
        try:
            with self.runtime_data_path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        users = payload.get("users", [])
        if not isinstance(users, list):
            return {}
        return {str(user.get("user_id")): user for user in users if isinstance(user, dict) and user.get("user_id")}

    def _profile_from_runtime(self, user_id: str) -> UserProfile | None:
        raw = self._load_runtime_profiles().get(user_id)
        if raw is None:
            return None
        try:
            return UserProfile.model_validate(raw)
        except ValueError:
            return None

    def _save_runtime_profile(self, profile: UserProfile) -> None:
        profiles = self._load_runtime_profiles()
        profiles[profile.user_id] = profile.model_dump()
        self.runtime_data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"users": list(profiles.values())}
        with self.runtime_data_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def _should_persist_long_term_profile(self, message: str) -> bool:
        if not message.strip():
            return True
        text = message.strip()
        trip_only_terms = ["这次", "本次", "今天", "今晚", "当前", "这条路线", "这个路线", "刚刚", "临时"]
        long_term_terms = ["以后", "下次", "一直", "长期", "默认", "每次", "都", "我喜欢", "我不喜欢", "我的偏好", "记住"]
        if any(term in text for term in long_term_terms):
            return True
        if any(term in text for term in trip_only_terms):
            return False
        return False

    def _profile_from_seed(self, user_id: str) -> UserProfile | None:
        raw = self._seed_profiles.get(user_id)
        if raw is None:
            return None

        soft_preferences = (
            raw.get("current_trip", {})
            .get("soft_preferences", {})
        )
        interest_tags = normalize_interest_preferences(self._as_string_list(soft_preferences.get("prefer_tags")))
        optimization_goals = normalize_goal_preferences(self._as_string_list(soft_preferences.get("prefer_tags")))
        preferences = legacy_preferences_from_layers(interest_tags, optimization_goals)
        avoid_tags = normalize_avoid_tags(self._as_string_list(soft_preferences.get("avoid_tags")))
        preference_profile = raw.get("preference_profile", {})
        history_behavior = raw.get("history_behavior", {})
        return UserProfile(
            user_id=user_id,
            tags=preferences,
            preferences=preferences,
            interest_tags=interest_tags,
            optimization_goals=optimization_goals,
            avoid_tags=avoid_tags,
            preference_weights=self._weights_from_seed(raw),
            budget_sensitivity=self._to_float(preference_profile.get("budget_sensitivity"), 0.5),
            walking_tolerance=self._to_float(preference_profile.get("walking_tolerance"), 0.5),
            crowd_tolerance=self._to_float(preference_profile.get("crowd_tolerance"), 0.5),
            schedule_tightness=self._to_float(preference_profile.get("schedule_tightness"), 0.5),
            novelty_preference=self._to_float(preference_profile.get("novelty_preference"), 0.5),
            comfort_preference=self._to_float(preference_profile.get("comfort_preference"), 0.5),
            category_preferences=self._score_map(raw.get("category_preferences")),
            preferred_route_roles=self._route_roles_from_terms(preferences),
            preferred_experience_tags=self._experience_tags_from_terms(preferences),
            preferred_time_slots=self._time_slots_from_terms(preferences),
            preferred_transport_modes=self._transport_modes_from_terms(preferences),
            liked_poi_ids=self._as_string_list(history_behavior.get("liked_poi_ids")),
            disliked_poi_ids=self._as_string_list(history_behavior.get("disliked_poi_ids")),
            skipped_categories=self._as_string_list(history_behavior.get("skipped_categories")),
            common_adjust_actions=self._as_string_list(history_behavior.get("common_adjust_actions")),
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

    def _score_map(self, value: object) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, float] = {}
        for key, raw_score in value.items():
            result[str(key)] = self._to_float(raw_score, 0)
        return result

    def _optional_score(self, value: float | None, default: float = 0.5) -> float:
        if value is None:
            return default
        return max(0, min(1, self._to_float(value, default)))

    def _bump(self, value: float, amount: float) -> float:
        return round(max(0, min(1, value + amount)), 3)

    def _updated_budget_sensitivity(self, profile: UserProfile, terms: list[str]) -> float:
        if any(term in terms for term in ["省钱", "太贵"]):
            return self._bump(profile.budget_sensitivity, 0.08)
        return profile.budget_sensitivity

    def _updated_walking_tolerance(self, profile: UserProfile, terms: list[str]) -> float:
        if any(term in terms for term in ["少走路", "步行多"]):
            return self._bump(profile.walking_tolerance, -0.08)
        return profile.walking_tolerance

    def _updated_crowd_tolerance(self, profile: UserProfile, terms: list[str]) -> float:
        if any(term in terms for term in ["少排队", "排队久", "人流密集"]):
            return self._bump(profile.crowd_tolerance, -0.08)
        return profile.crowd_tolerance

    def _updated_novelty_preference(self, profile: UserProfile, terms: list[str]) -> float:
        if any(term in terms for term in ["小众", "文艺", "拍照"]):
            return self._bump(profile.novelty_preference, 0.05)
        return profile.novelty_preference

    def _updated_comfort_preference(self, profile: UserProfile, terms: list[str]) -> float:
        if any(term in terms for term in ["室内", "安静", "亲子"]):
            return self._bump(profile.comfort_preference, 0.05)
        return profile.comfort_preference

    def _merged_category_preferences(self, profile: UserProfile, terms: list[str]) -> dict[str, float]:
        categories = dict(profile.category_preferences)
        for category in self._categories_from_terms(terms):
            categories[category] = max(categories.get(category, 0.5), 0.75)
        return categories

    def _categories_from_terms(self, terms: list[str]) -> list[str]:
        mapping = {
            "美食": ["restaurant"],
            "咖啡": ["cafe"],
            "拍照": ["landmark", "night_view"],
            "citywalk": ["landmark", "market"],
            "逛店": ["boutique", "bookstore", "lifestyle_store", "toy_collectible", "design_store"],
            "购物": ["shopping", "boutique", "lifestyle_store"],
            "书店": ["bookstore"],
            "买手店": ["boutique"],
            "潮玩": ["toy_collectible"],
            "美妆": ["beauty_retail"],
            "户外": ["sports_outdoor"],
            "文创": ["design_store"],
            "室内": ["museum", "gallery", "shopping"],
            "雨天": ["museum", "gallery", "shopping"],
            "亲子": ["park", "museum"],
            "夜景": ["night_view"],
            "晚上": ["night_view"],
        }
        return self._mapped_terms(terms, mapping)

    def _route_roles_from_terms(self, terms: list[str]) -> list[str]:
        mapping = {
            "美食": ["meal"],
            "咖啡": ["coffee_break", "rest_stop"],
            "拍照": ["photo_stop"],
            "citywalk": ["main_activity", "photo_stop"],
            "逛店": ["main_activity", "photo_stop", "rest_stop"],
            "购物": ["main_activity", "rest_stop"],
            "少走路": ["transit_anchor", "rest_stop"],
            "室内": ["main_activity", "rest_stop"],
            "夜景": ["night_end"],
        }
        return self._mapped_terms(terms, mapping)

    def _experience_tags_from_terms(self, terms: list[str]) -> list[str]:
        mapping = {
            "美食": ["本地", "老字号"],
            "拍照": ["拍照", "经典"],
            "citywalk": ["文艺", "本地"],
            "逛店": ["小众", "文艺"],
            "购物": ["小众", "高性价比"],
            "书店": ["安静", "文艺"],
            "买手店": ["小众", "设计"],
            "潮玩": ["小众"],
            "美妆": ["香氛"],
            "文创": ["文艺", "设计"],
            "室内": ["雨天", "展览"],
            "安静": ["安静", "小众"],
            "亲子": ["亲子"],
            "省钱": ["免费", "高性价比"],
        }
        return self._mapped_terms(terms, mapping)

    def _time_slots_from_terms(self, terms: list[str]) -> list[str]:
        mapping = {
            "夜景": ["evening", "night"],
            "晚上": ["evening", "night"],
            "咖啡": ["afternoon"],
        }
        return self._mapped_terms(terms, mapping)

    def _transport_modes_from_terms(self, terms: list[str]) -> list[str]:
        mapping = {
            "公共交通": ["metro", "bus"],
            "公交优先": ["bus", "metro"],
            "地铁优先": ["metro", "bus"],
            "公交": ["bus", "metro"],
            "地铁": ["metro", "bus"],
            "不打车": ["metro", "bus", "walk"],
            "少走路": ["metro", "taxi"],
            "省钱": ["metro", "bus", "walk"],
            "亲子": ["taxi", "metro"],
        }
        return self._mapped_terms(terms, mapping)

    def _mapped_terms(self, terms: list[str], mapping: dict[str, list[str]]) -> list[str]:
        values: list[str] = []
        for term in terms:
            for key, mapped in mapping.items():
                if key in term or term in key:
                    values.extend(mapped)
        return self._unique(values)

    def _to_float(self, value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
