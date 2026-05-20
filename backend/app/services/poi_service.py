import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import UserProfile


@dataclass(frozen=True)
class POICandidate:
    poi: POI
    search_text: str
    risk_text: str
    rainy_day_score: float
    friends_score: float
    budget_score: float


class POIService:
    """B-owned module: filters POI candidates by intent and strategy tags."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[3] / "data" / "seed" / "pois.json"
        self._candidates = self._load_candidates()

    def search(self, intent: Intent, user_profile: UserProfile | None = None, limit: int = 20) -> list[POI]:
        city_matches = [candidate for candidate in self._candidates if candidate.poi.city == intent.city]
        if not city_matches:
            return []

        strict_matches = [
            candidate
            for candidate in city_matches
            if self._matches_budget(candidate.poi, intent)
            and self._matches_preferences(candidate, intent)
            and not self._matches_avoid_tags(candidate, intent)
        ]
        candidates = strict_matches or [
            candidate
            for candidate in city_matches
            if not self._matches_avoid_tags(candidate, intent)
            and self._is_not_extreme_budget_mismatch(candidate.poi, intent)
        ]
        if not candidates:
            candidates = city_matches

        ranked = sorted(
            candidates,
            key=lambda candidate: self._rank_score(candidate, intent, user_profile),
            reverse=True,
        )
        return [candidate.poi for candidate in ranked[:limit]]

    def _load_candidates(self) -> list[POICandidate]:
        with self.data_path.open(encoding="utf-8") as file:
            payload = json.load(file)
        return [self._candidate_from_raw(raw) for raw in payload.get("pois", [])]

    def _candidate_from_raw(self, raw: dict[str, Any]) -> POICandidate:
        location = raw.get("location", {})
        visit_info = raw.get("visit_info", {})
        quality = raw.get("quality", {})
        suitability = raw.get("suitability", {})
        planning = raw.get("planning_features", {})

        tags = self._as_string_list(raw.get("tags"))
        highlight_tags = self._as_string_list(raw.get("highlight_text_tags"))
        risk_flags = self._as_string_list(planning.get("risk_flags"))
        avoid_reasons = self._as_string_list(planning.get("avoid_reasons"))
        negative_tags = risk_flags + avoid_reasons
        price_min = self._to_int(visit_info.get("price_min"), 0)
        price_max = self._to_int(visit_info.get("price_max"), price_min)
        avg_price = round((price_min + price_max) / 2)

        poi = POI(
            id=str(raw.get("poi_id", "")),
            name=str(raw.get("name", "")),
            city=str(location.get("city", "")),
            category=str(raw.get("category", "")),
            lat=self._to_float(location.get("lat"), 0),
            lng=self._to_float(location.get("lng"), 0),
            avg_price=avg_price,
            rating=self._to_float(quality.get("rating"), 0),
            queue_minutes=self._to_int(quality.get("live_queue_time_min") or quality.get("queue_time_min"), 0),
            visit_duration_minutes=self._to_int(visit_info.get("avg_visit_duration_min"), 60),
            open_hours=f"{visit_info.get('open_time', '00:00')}-{visit_info.get('close_time', '23:59')}",
            tags=tags + [tag for tag in highlight_tags if tag not in tags],
            negative_tags=negative_tags,
            family_friendly=self._to_float(suitability.get("family"), 0),
            indoor=bool(planning.get("indoor", False)),
        )
        searchable_parts = [
            poi.name,
            poi.category,
            raw.get("highlight_text", ""),
            raw.get("ugc_tip", ""),
            planning.get("meal_type", ""),
            *poi.tags,
        ]
        risk_parts = [*poi.negative_tags, *self._as_string_list(raw.get("negative_tags"))]
        return POICandidate(
            poi=poi,
            search_text=" ".join(str(part) for part in searchable_parts if part),
            risk_text=" ".join(str(part) for part in risk_parts if part),
            rainy_day_score=self._to_float(suitability.get("rainy_day"), 0),
            friends_score=self._to_float(suitability.get("friends"), 0),
            budget_score=self._to_float(suitability.get("budget_friendly"), 0),
        )

    def _matches_budget(self, poi: POI, intent: Intent) -> bool:
        return poi.avg_price <= intent.budget_per_person

    def _is_not_extreme_budget_mismatch(self, poi: POI, intent: Intent) -> bool:
        return poi.avg_price <= max(intent.budget_per_person * 1.5, intent.budget_per_person + 80)

    def _matches_preferences(self, candidate: POICandidate, intent: Intent) -> bool:
        preferences = self._normalize_terms(intent.preferences)
        if not preferences:
            return True
        return any(self._term_matches(term, candidate.search_text) for term in preferences)

    def _matches_avoid_tags(self, candidate: POICandidate, intent: Intent) -> bool:
        avoid_tags = self._normalize_terms(intent.avoid_tags)
        return any(
            self._term_matches(term, candidate.search_text) or self._term_matches(term, candidate.risk_text)
            for term in avoid_tags
        )

    def _rank_score(self, candidate: POICandidate, intent: Intent, user_profile: UserProfile | None) -> float:
        poi = candidate.poi
        weights = user_profile.preference_weights if user_profile else {}
        quality_weight = self._weight(weights, "quality", 0.3)
        queue_weight = self._weight(weights, "queue", 0.25)
        distance_weight = self._weight(weights, "distance", 0.2)
        budget_weight = self._weight(weights, "budget", 0.15)
        preference_weight = self._weight(weights, "preference", 0.1)

        distance_km = self._distance_from_intent(poi, intent)
        distance_score = 1 if distance_km is None else max(0, 1 - min(distance_km, 20) / 20)
        budget_score = max(0, 1 - min(poi.avg_price, intent.budget_per_person) / max(intent.budget_per_person, 1))
        if poi.avg_price <= intent.budget_per_person:
            budget_score = max(budget_score, candidate.budget_score)
        queue_score = max(0, 1 - min(poi.queue_minutes, 90) / 90)
        quality_score = min(max((poi.rating - 3) / 2, 0), 1)

        intent_terms = self._normalize_terms(intent.preferences)
        profile_terms = self._normalize_terms(user_profile.tags if user_profile else [])
        preference_score = self._match_ratio(intent_terms, candidate.search_text)
        profile_score = self._match_ratio(profile_terms, candidate.search_text)
        scenario_score = self._scenario_score(candidate, intent)

        score = (
            quality_score * quality_weight
            + queue_score * queue_weight
            + distance_score * distance_weight
            + budget_score * budget_weight
            + preference_score * preference_weight
            + profile_score * 0.2
            + scenario_score * 0.1
        )
        if distance_km is not None:
            score += distance_score * 0.45
        if self._has_term(intent_terms + profile_terms, "少排队"):
            score += queue_score * 0.25
        if self._has_term(intent_terms + profile_terms, "吃好") and poi.category == "restaurant":
            score += quality_score * 0.25
        if self._has_term(intent_terms + profile_terms, "citywalk"):
            score += self._term_bonus(candidate, ["citywalk", "拍照", "街区", "散步", "landmark"]) * 0.2
        if self._has_term(intent_terms + profile_terms, "室内") or self._has_term(intent_terms + profile_terms, "雨天"):
            score += (1 if poi.indoor else candidate.rainy_day_score) * 0.2
        return score

    def _scenario_score(self, candidate: POICandidate, intent: Intent) -> float:
        if intent.scenario == "friends_citywalk":
            return max(candidate.friends_score, self._term_bonus(candidate, ["朋友", "拍照", "citywalk", "夜景", "咖啡"]))
        return 0

    def _distance_from_intent(self, poi: POI, intent: Intent) -> float | None:
        if intent.start_lat is None or intent.start_lng is None:
            return None
        return self._haversine_km(intent.start_lat, intent.start_lng, poi.lat, poi.lng)

    def _haversine_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radius_km = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        )
        return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _match_ratio(self, terms: list[str], text: str) -> float:
        if not terms:
            return 0
        matches = sum(1 for term in terms if self._term_matches(term, text))
        return matches / len(terms)

    def _term_bonus(self, candidate: POICandidate, terms: list[str]) -> float:
        return self._match_ratio(self._normalize_terms(terms), candidate.search_text)

    def _term_matches(self, term: str, text: str) -> bool:
        aliases = {
            "少排队": ["少排队", "别排队", "不排队", "排队可接受", "queue"],
            "吃好": ["吃好", "美食", "餐厅", "聚餐", "菜", "restaurant"],
            "更省钱": ["省钱", "便宜", "免费", "budget"],
            "少走路": ["少走路", "轻松", "交通", "metro"],
            "citywalk": ["citywalk", "街区", "散步", "漫步", "拍照", "landmark"],
            "室内": ["室内", "雨天", "museum", "gallery", "theater", "cafe", "shopping"],
            "雨天": ["雨天", "室内", "museum", "gallery", "theater", "cafe", "shopping"],
            "拍照": ["拍照", "夜景", "出片", "photo"],
            "人流密集": ["人流密集", "拥挤", "人多", "long_queue"],
            "排队久": ["排队久", "long_queue", "排队"],
            "太贵": ["太贵", "高价", "贵"],
        }
        lowered = text.lower()
        values = aliases.get(term, [term])
        return any(value.lower() in lowered for value in values)

    def _has_term(self, terms: list[str], target: str) -> bool:
        return any(term == target or self._term_matches(term, target) or self._term_matches(target, term) for term in terms)

    def _normalize_terms(self, terms: list[str]) -> list[str]:
        return [term.strip() for term in terms if term and term.strip()]

    def _weight(self, weights: dict[str, float], key: str, default: float) -> float:
        value = weights.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _as_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]

    def _to_int(self, value: object, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _to_float(self, value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
