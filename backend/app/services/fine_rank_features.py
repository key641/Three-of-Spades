import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyTag, UserProfile


POSITIVE_EVENT_TYPES = {"click", "save", "like", "selected_in_route", "completed_visit"}
NEGATIVE_EVENT_TYPES = {"skip", "replace", "dislike"}
FEATURE_SCHEMA_VERSION = "fine_rank_features_v1"


@dataclass(frozen=True)
class FineRankStats:
    poi_positive_counts: dict[str, int] = field(default_factory=dict)
    poi_negative_counts: dict[str, int] = field(default_factory=dict)
    category_positive_counts: dict[str, int] = field(default_factory=dict)
    category_negative_counts: dict[str, int] = field(default_factory=dict)


def build_stats(events: list[dict[str, Any]], poi_by_id: dict[str, POI]) -> FineRankStats:
    poi_positive: Counter[str] = Counter()
    poi_negative: Counter[str] = Counter()
    category_positive: Counter[str] = Counter()
    category_negative: Counter[str] = Counter()
    for event in events:
        poi_id = str(event.get("poi_id", ""))
        poi = poi_by_id.get(poi_id)
        if poi is None:
            continue
        event_type = str(event.get("event_type", ""))
        if event_type in POSITIVE_EVENT_TYPES:
            poi_positive[poi_id] += 1
            category_positive[poi.category] += 1
        elif event_type in NEGATIVE_EVENT_TYPES:
            poi_negative[poi_id] += 1
            category_negative[poi.category] += 1
    return FineRankStats(
        poi_positive_counts=dict(poi_positive),
        poi_negative_counts=dict(poi_negative),
        category_positive_counts=dict(category_positive),
        category_negative_counts=dict(category_negative),
    )


def build_features(
    poi: POI,
    intent: Intent,
    user_profile: UserProfile,
    strategy_tags: list[StrategyTag] | None = None,
    objective: str = "balanced",
    stats: FineRankStats | None = None,
    event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = stats or FineRankStats()
    context = event_context or {}
    preferences = _normalize_terms(
        [
            *intent.preferences,
            *user_profile.tags,
            *user_profile.preferences,
            *[str(item) for item in context.get("preferences", []) if item],
        ]
    )
    avoid_terms = _normalize_terms([*intent.avoid_tags, *user_profile.avoid_tags])
    route_roles = set(poi.route_roles)
    experience_tags = set(poi.experience_tags + poi.tags + poi.highlight_text_tags)
    category_pref = max(
        user_profile.category_preferences.get(poi.category, 0),
        user_profile.category_preferences.get(poi.primary_category, 0),
        *(user_profile.category_preferences.get(category, 0) for category in poi.secondary_categories),
    )
    route_role_match = _ratio(user_profile.preferred_route_roles, route_roles)
    experience_match = _ratio(user_profile.preferred_experience_tags, experience_tags)
    preference_match = _match_ratio(preferences, _poi_text(poi))
    avoid_match = _match_ratio(avoid_terms, _poi_text(poi, include_risk=True))
    strategy_match = _match_ratio([tag.tag for tag in strategy_tags or [] if tag.polarity != "avoid"], _poi_text(poi))
    objective_match = _objective_match(poi, objective)
    budget = _number(context.get("budget_per_person"), intent.budget_per_person)
    price_ratio = poi.avg_price / max(float(budget), 1)
    same_category_total = stats.category_positive_counts.get(poi.category, 0) + stats.category_negative_counts.get(poi.category, 0)
    same_category_positive_rate = (stats.category_positive_counts.get(poi.category, 0) + 1) / max(same_category_total + 2, 1)
    poi_total = stats.poi_positive_counts.get(poi.id, 0) + stats.poi_negative_counts.get(poi.id, 0)
    poi_positive_rate = (stats.poi_positive_counts.get(poi.id, 0) + 1) / max(poi_total + 2, 1)

    return {
        "user_budget_sensitivity": user_profile.budget_sensitivity,
        "user_walking_tolerance": user_profile.walking_tolerance,
        "user_crowd_tolerance": user_profile.crowd_tolerance,
        "user_novelty_preference": user_profile.novelty_preference,
        "user_comfort_preference": user_profile.comfort_preference,
        "user_category_preference": category_pref,
        "user_liked_this_poi": poi.id in user_profile.liked_poi_ids,
        "user_disliked_this_poi": poi.id in user_profile.disliked_poi_ids,
        "user_skipped_this_category": poi.category in user_profile.skipped_categories,
        "poi_category": poi.category,
        "poi_primary_category": poi.primary_category,
        "poi_rating": poi.rating,
        "poi_review_log": math.log1p(max(poi.review_count, 0)),
        "poi_price": poi.avg_price,
        "poi_price_ratio": price_ratio,
        "poi_indoor": poi.indoor,
        "poi_walking_intensity": poi.walking_intensity,
        "poi_popularity": poi.popularity,
        "poi_queue_minutes": poi.queue_minutes,
        "poi_crowd_level": poi.crowd_level,
        "poi_live_crowd_level": poi.live_crowd_level,
        "poi_rainy_day_score": poi.rainy_day_score,
        "poi_budget_friendly": poi.budget_friendly,
        "poi_photo_friendly": poi.photo_friendly,
        "poi_night_activity": poi.night_activity,
        "poi_positive_rate": poi_positive_rate,
        "poi_positive_count_log": math.log1p(stats.poi_positive_counts.get(poi.id, 0)),
        "poi_negative_count_log": math.log1p(stats.poi_negative_counts.get(poi.id, 0)),
        "same_category_positive_rate": same_category_positive_rate,
        "preference_match": preference_match,
        "avoid_match": avoid_match,
        "strategy_match": strategy_match,
        "route_role_match": route_role_match,
        "experience_match": experience_match,
        "objective_match": objective_match,
        "context_city": str(context.get("city") or intent.city),
        "context_weather": str(context.get("weather") or "unknown"),
        "context_time_slot": str(context.get("time_slot") or _time_slot(intent.start_time)),
        "context_scenario": str(context.get("scenario") or intent.scenario),
        "context_route_objective": str(context.get("route_objective") or objective),
        "context_people_count": intent.people_count,
        "context_budget_per_person": budget,
        "has_meal_role": "meal" in route_roles,
        "has_main_activity_role": "main_activity" in route_roles,
        "has_rest_role": bool({"rest_stop", "coffee_break"} & route_roles),
        "has_photo_role": "photo_stop" in route_roles,
        "has_transit_role": "transit_anchor" in route_roles,
        "has_night_role": "night_end" in route_roles,
    }


def label_for_event(event_type: str) -> dict[str, int]:
    return {
        "click": int(event_type in {"click", "save", "selected_in_route"}),
        "like": int(event_type in {"like", "completed_visit"}),
        "skip": int(event_type in NEGATIVE_EVENT_TYPES),
    }


def feature_names(features: list[dict[str, Any]]) -> dict[str, list[str]]:
    numeric: set[str] = set()
    categorical: set[str] = set()
    boolean: set[str] = set()
    for feature in features:
        for key, value in feature.items():
            if isinstance(value, bool):
                boolean.add(key)
            elif isinstance(value, (int, float)):
                numeric.add(key)
            else:
                categorical.add(key)
    return {
        "numeric": sorted(numeric),
        "boolean": sorted(boolean),
        "categorical": sorted(categorical),
    }


def _poi_text(poi: POI, include_risk: bool = False) -> str:
    parts = [
        poi.name,
        poi.category,
        poi.primary_category,
        poi.meal_type,
        poi.highlight_text,
        poi.ugc_tip,
        poi.walking_intensity,
        *poi.secondary_categories,
        *poi.route_roles,
        *poi.experience_tags,
        *poi.tags,
        *poi.highlight_text_tags,
        *poi.suitable_time_slots,
    ]
    if include_risk:
        parts.extend([*poi.negative_tags, *poi.risk_flags, *poi.avoid_reasons])
    return " ".join(str(part) for part in parts if part).lower()


def _objective_match(poi: POI, objective: str) -> float:
    if objective == "budget":
        return poi.budget_friendly
    if objective == "low_walking":
        return {"low": 1.0, "medium": 0.55, "high": 0.1}.get(poi.walking_intensity, 0.45)
    if objective == "food_first":
        return 1.0 if poi.category in {"restaurant", "cafe", "market"} or "meal" in poi.route_roles else 0.0
    if objective == "photo_food":
        food = 1.0 if poi.category in {"restaurant", "cafe", "market"} else 0.0
        return max(food * 0.6, poi.photo_friendly)
    if objective == "nature_relax":
        return 1.0 if poi.primary_category == "nature" or poi.category == "park" else 0.0
    if objective == "photo_citywalk":
        return max(poi.photo_friendly, 1.0 if "photo_stop" in poi.route_roles else 0.0)
    if objective == "indoor_rainy":
        return max(1.0 if poi.indoor else 0.0, poi.rainy_day_score)
    if objective == "night_friendly":
        return poi.night_activity
    return 0.5


def _match_ratio(terms: list[str], text: str) -> float:
    if not terms:
        return 0.0
    return sum(1 for term in terms if term.lower() in text) / len(terms)


def _ratio(preferred: list[str], actual: set[str]) -> float:
    terms = _normalize_terms(preferred)
    if not terms:
        return 0.0
    return len(set(terms) & actual) / len(terms)


def _normalize_terms(terms: list[str]) -> list[str]:
    return [term.strip() for term in terms if term and term.strip()]


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _time_slot(value: str) -> str:
    try:
        hour = int(value.split(":")[0])
    except (ValueError, IndexError):
        return "unknown"
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"
