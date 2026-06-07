import math
from dataclasses import dataclass, field
from typing import Any

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyTag, UserProfile
from app.services.strategy_service import StrategyService


@dataclass(frozen=True)
class CoarseRankResult:
    candidate: Any
    score: float
    features: dict[str, float] = field(default_factory=dict)


class CoarseRankService:
    """Fast rule-based coarse ranker after multi-channel POI recall."""

    def __init__(self, strategy_service: StrategyService | None = None) -> None:
        self.strategy_service = strategy_service or StrategyService()

    def rank(
        self,
        candidates: list[Any],
        intent: Intent,
        user_profile: UserProfile | None = None,
        strategy_tags: list[StrategyTag] | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        ranked = sorted(
            candidates,
            key=lambda candidate: self.score(candidate, intent, user_profile, strategy_tags or []),
            reverse=True,
        )
        if limit is None:
            return ranked
        if limit >= 40:
            return self._select_diverse(ranked, limit)
        return ranked[:limit]

    def rank_with_features(
        self,
        candidates: list[Any],
        intent: Intent,
        user_profile: UserProfile | None = None,
        strategy_tags: list[StrategyTag] | None = None,
        limit: int | None = None,
    ) -> list[CoarseRankResult]:
        results = [
            CoarseRankResult(
                candidate=candidate,
                score=self.score(candidate, intent, user_profile, strategy_tags or []),
                features=self.features(candidate, intent, user_profile, strategy_tags or []),
            )
            for candidate in candidates
        ]
        ranked = sorted(results, key=lambda item: item.score, reverse=True)
        if limit is None:
            return ranked
        if limit >= 40:
            selected_candidates = self._select_diverse([item.candidate for item in ranked], limit)
            selected_ids = [candidate.poi.id for candidate in selected_candidates]
            by_id = {item.candidate.poi.id: item for item in ranked}
            return [by_id[poi_id] for poi_id in selected_ids if poi_id in by_id]
        return ranked[:limit]

    def score(
        self,
        candidate: Any,
        intent: Intent,
        user_profile: UserProfile | None,
        strategy_tags: list[StrategyTag] | None = None,
    ) -> float:
        features = self.features(candidate, intent, user_profile, strategy_tags or [])
        weights = user_profile.preference_weights if user_profile else {}
        quality_weight = self._weight(weights, "quality", 0.3)
        queue_weight = self._weight(weights, "queue", 0.25)
        distance_weight = self._weight(weights, "distance", 0.2)
        budget_weight = self._weight(weights, "budget", 0.15)
        preference_weight = self._weight(weights, "preference", 0.1)

        score = (
            features["quality"] * quality_weight
            + features["queue_crowd"] * queue_weight
            + features["distance_fit"] * distance_weight
            + features["budget_fit"] * budget_weight
            + features["preference_match"] * preference_weight
            + features["profile_tag_match"] * 0.2
            + features["profile_fit"] * 0.25
            + features["scenario_fit"] * 0.1
            + features["time_fit"] * 0.12
            + features["strategy_tag_match"] * 0.45
            - features["avoid_risk"] * 0.55
        )

        distance_km = self._distance_from_intent(candidate.poi, intent)
        intent_terms = self._normalize_terms(intent.preferences)
        profile_terms = self._normalize_terms(user_profile.tags if user_profile else [])
        poi = candidate.poi
        if user_profile and poi.id in user_profile.liked_poi_ids:
            score += 0.4
        if user_profile and poi.id in user_profile.disliked_poi_ids:
            score -= 0.8
        if user_profile and poi.category in user_profile.skipped_categories:
            score -= 0.5
        if distance_km is not None:
            score += features["distance_fit"] * 0.45
        if self._has_term(intent_terms + profile_terms, "少排队"):
            score += features["queue_crowd"] * 0.25
        if self._has_term(intent_terms + profile_terms, "吃好"):
            score += self._meal_score(poi, ["吃好"]) * 0.4
        if self._has_term(intent_terms + profile_terms, "咖啡"):
            score += self._meal_score(poi, ["咖啡"]) * 0.4
        if self._has_term(intent_terms + profile_terms, "轻食") or self._has_term(intent_terms + profile_terms, "小吃"):
            score += self._meal_score(poi, ["轻食"]) * 0.35
        if self._has_term(intent_terms + profile_terms, "citywalk"):
            score += self._term_bonus(candidate, ["citywalk", "拍照", "街区", "散步", "landmark"]) * 0.2
        if self._has_term(intent_terms + profile_terms, "室内") or self._has_term(intent_terms + profile_terms, "雨天"):
            score += (1 if poi.indoor else poi.rainy_day_score) * 0.25
        if self._has_term(intent_terms + profile_terms, "少走路") or self._has_term(intent_terms + profile_terms, "轻松"):
            score += self._walking_score(poi) * 0.3
        return score

    def features(
        self,
        candidate: Any,
        intent: Intent,
        user_profile: UserProfile | None,
        strategy_tags: list[StrategyTag] | None = None,
    ) -> dict[str, float]:
        poi = candidate.poi
        distance_km = self._distance_from_intent(poi, intent)
        distance_score = 1 if distance_km is None else max(0, 1 - min(distance_km, 20) / 20)
        budget_score = max(0, 1 - min(poi.avg_price, intent.budget_per_person) / max(intent.budget_per_person, 1))
        if poi.avg_price <= intent.budget_per_person:
            budget_score = max(budget_score, poi.budget_friendly)
        elif poi.avg_price <= intent.budget_per_person * 1.5:
            budget_score = max(budget_score, 0.45)
        elif poi.avg_price > intent.budget_per_person * 2:
            budget_score *= 0.25

        queue_score = max(
            0,
            1
            - min(poi.queue_minutes, 90) / 120
            - min(max(poi.live_crowd_level, poi.crowd_level), 1) * 0.25,
        )
        intent_terms = self._normalize_terms(intent.preferences)
        profile_terms = self._normalize_terms(user_profile.tags if user_profile else [])
        return {
            "preference_match": self._match_ratio(intent_terms, candidate.search_text),
            "budget_fit": budget_score,
            "queue_crowd": queue_score,
            "quality": self._quality_score(poi),
            "distance_fit": distance_score,
            "time_fit": self._time_score(poi, intent),
            "avoid_risk": self._avoid_risk(candidate, intent, user_profile),
            "profile_fit": self._profile_dimension_score(candidate, user_profile),
            "profile_tag_match": self._match_ratio(profile_terms, candidate.search_text),
            "scenario_fit": self._scenario_score(candidate, intent),
            "strategy_tag_match": self.strategy_service.tag_score(poi, strategy_tags or []),
        }

    def _avoid_risk(self, candidate: Any, intent: Intent, user_profile: UserProfile | None) -> float:
        avoid_terms = self._normalize_terms([*intent.avoid_tags, *(user_profile.avoid_tags if user_profile else [])])
        if not avoid_terms:
            return 0
        text = f"{candidate.search_text} {candidate.risk_text}"
        return self._match_ratio(avoid_terms, text)

    def _select_diverse(self, ranked: list[Any], limit: int) -> list[Any]:
        category_cap = max(1, int(limit * 0.25))
        primary_cap = max(1, int(limit * 0.35))
        selected: list[Any] = []
        deferred: list[Any] = []
        category_counts: dict[str, int] = {}
        primary_counts: dict[str, int] = {}

        for candidate in ranked:
            category = candidate.poi.category
            primary_category = candidate.poi.primary_category
            if category_counts.get(category, 0) >= category_cap or primary_counts.get(primary_category, 0) >= primary_cap:
                deferred.append(candidate)
                continue
            selected.append(candidate)
            category_counts[category] = category_counts.get(category, 0) + 1
            primary_counts[primary_category] = primary_counts.get(primary_category, 0) + 1
            if len(selected) >= limit:
                return selected

        seen = {candidate.poi.id for candidate in selected}
        for candidate in deferred + ranked:
            if candidate.poi.id in seen:
                continue
            selected.append(candidate)
            seen.add(candidate.poi.id)
            if len(selected) >= limit:
                break
        return selected

    def _profile_dimension_score(self, candidate: Any, user_profile: UserProfile | None) -> float:
        if user_profile is None:
            return 0

        poi = candidate.poi
        score_parts: list[float] = []

        category_score = max(
            user_profile.category_preferences.get(poi.category, 0),
            user_profile.category_preferences.get(poi.primary_category, 0),
            *(user_profile.category_preferences.get(category, 0) for category in poi.secondary_categories),
        )
        if category_score:
            score_parts.append(category_score)

        if user_profile.preferred_route_roles:
            role_hits = len(set(user_profile.preferred_route_roles) & set(poi.route_roles))
            score_parts.append(min(1, role_hits / max(len(user_profile.preferred_route_roles), 1)))

        if user_profile.preferred_experience_tags:
            poi_experience = set(poi.experience_tags + poi.tags + poi.highlight_text_tags)
            experience_hits = len(set(user_profile.preferred_experience_tags) & poi_experience)
            score_parts.append(min(1, experience_hits / max(len(user_profile.preferred_experience_tags), 1)))

        if user_profile.preferred_time_slots:
            time_hits = len(set(user_profile.preferred_time_slots) & set(poi.suitable_time_slots))
            score_parts.append(min(1, time_hits / max(len(user_profile.preferred_time_slots), 1)))

        if user_profile.preferred_transport_modes:
            transport_hits = len(set(user_profile.preferred_transport_modes) & set(poi.recommended_transport))
            score_parts.append(min(1, transport_hits / max(len(user_profile.preferred_transport_modes), 1)))

        if not score_parts:
            return 0
        return sum(score_parts) / len(score_parts)

    def _scenario_score(self, candidate: Any, intent: Intent) -> float:
        if intent.scenario == "friends_citywalk":
            return max(candidate.poi.friends_friendly, self._term_bonus(candidate, ["朋友", "拍照", "citywalk", "夜景", "咖啡"]))
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

    def _term_bonus(self, candidate: Any, terms: list[str]) -> float:
        return self._match_ratio(self._normalize_terms(terms), candidate.search_text)

    def _term_matches(self, term: str, text: str) -> bool:
        aliases = {
            "少排队": ["少排队", "别排队", "不排队", "排队可接受", "queue"],
            "吃好": ["吃好", "美食", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining"],
            "food_first": ["吃好", "美食", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining"],
            "photo_food": ["拍照", "出片", "好看", "环境", "餐厅", "美食", "restaurant", "photo"],
            "nature": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "nature_relax": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "咖啡": ["咖啡", "下午茶", "休息", "cafe"],
            "轻食": ["轻食", "小吃", "light_meal", "fast_food", "market"],
            "小吃": ["小吃", "轻食", "light_meal", "fast_food", "market"],
            "更省钱": ["省钱", "便宜", "免费", "budget"],
            "少走路": ["少走路", "轻松", "交通", "metro", "low"],
            "low_walking": ["少走路", "轻松", "交通", "metro", "low"],
            "轻松": ["少走路", "轻松", "low", "metro"],
            "citywalk": ["citywalk", "街区", "散步", "漫步", "拍照", "landmark"],
            "逛店": ["逛店", "逛街", "购物", "买手店", "书店", "生活方式", "潮玩", "美妆", "设计商店", "shopping", "boutique", "bookstore", "lifestyle_store", "toy_collectible", "beauty_retail", "design_store"],
            "购物": ["逛店", "逛街", "购物", "商场", "买手店", "生活方式", "shopping", "boutique", "lifestyle_store"],
            "书店": ["书店", "书局", "阅读", "bookstore"],
            "买手店": ["买手店", "选品店", "设计师品牌", "boutique"],
            "潮玩": ["潮玩", "手办", "盲盒", "toy_collectible"],
            "美妆": ["美妆", "香氛", "护肤", "beauty_retail"],
            "户外": ["户外", "运动户外", "跑步", "骑行", "sports_outdoor"],
            "文创": ["文创", "设计商店", "艺术周边", "design_store"],
            "室内": ["室内", "雨天", "museum", "gallery", "theater", "cafe", "shopping"],
            "indoor_rainy": ["室内", "雨天", "museum", "gallery", "theater", "cafe", "shopping"],
            "雨天": ["雨天", "室内", "museum", "gallery", "theater", "cafe", "shopping"],
            "拍照": ["拍照", "夜景", "出片", "photo"],
            "photo": ["拍照", "夜景", "出片", "photo"],
            "晚上": ["晚上", "夜景", "夜游", "evening", "night", "night_view"],
            "night_view": ["晚上", "夜景", "夜游", "evening", "night", "night_view"],
            "夜游": ["夜游", "夜景", "晚上", "evening", "night", "night_view"],
            "亲子友好": ["亲子友好", "亲子", "儿童", "儿童友好", "family", "公园"],
            "亲子": ["亲子友好", "亲子", "儿童", "儿童友好", "family", "公园"],
            "安静": ["安静", "清净", "人少", "小众", "solo", "cafe"],
            "人少": ["人少", "安静", "清净", "小众", "少排队"],
            "本地感": ["本地感", "本地", "市井", "老字号", "local"],
            "艺术展": ["艺术展", "艺术", "展览", "gallery", "museum"],
            "情侣": ["情侣", "couple", "夜景", "咖啡", "演出"],
            "老人友好": ["老人友好", "长辈", "elderly", "少走路", "low"],
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

    def _quality_score(self, poi: POI) -> float:
        rating_score = min(max((poi.rating - 3) / 2, 0), 1)
        review_score = min(poi.review_count / 8000, 1)
        popularity_score = min(max(poi.popularity, 0), 1)
        return rating_score * 0.55 + review_score * 0.2 + popularity_score * 0.25

    def _meal_score(self, poi: POI, terms: list[str]) -> float:
        meal_type = poi.meal_type
        if any(term in {"吃好", "餐厅", "聚餐", "美食"} for term in terms):
            if poi.category == "restaurant" or meal_type in {"local_food", "fine_dining"}:
                return 1
            if meal_type in {"light_meal", "cafe", "fast_food"}:
                return 0.65
        if any(term in {"咖啡", "下午茶", "休息"} for term in terms):
            return 1 if meal_type == "cafe" or poi.category == "cafe" else 0
        if any(term in {"轻食", "小吃"} for term in terms):
            return 1 if meal_type in {"light_meal", "fast_food"} or poi.category == "market" else 0
        return 0

    def _walking_score(self, poi: POI) -> float:
        return {"low": 1, "medium": 0.55, "high": 0.1}.get(poi.walking_intensity, 0.45)

    def _time_score(self, poi: POI, intent: Intent) -> float:
        start_minutes = self._parse_time(intent.start_time)
        if start_minutes is None:
            return 0.5

        score = 0.4
        if self._is_within_time_window(start_minutes, poi.open_time, poi.close_time):
            score += 0.25
        if self._is_before_last_entry(start_minutes, poi.last_entry_time, poi.open_time, poi.close_time):
            score += 0.2

        slot = self._time_slot(start_minutes)
        if slot in poi.suitable_time_slots:
            score += 0.25
        if slot in {"evening", "night"}:
            score += poi.night_activity * 0.25
        return min(score, 1)

    def _parse_time(self, value: str) -> int | None:
        parts = value.split(":")
        if len(parts) < 2:
            return None
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return None

    def _time_slot(self, minutes: int) -> str:
        hour = minutes // 60
        if 5 <= hour < 11:
            return "morning"
        if 11 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 21:
            return "evening"
        return "night"

    def _is_within_time_window(self, minutes: int, open_time: str, close_time: str) -> bool:
        open_minutes = self._parse_time(open_time)
        close_minutes = self._parse_time(close_time)
        if open_minutes is None or close_minutes is None:
            return False
        return self._minutes_in_range(minutes, open_minutes, close_minutes)

    def _is_before_last_entry(self, minutes: int, last_entry_time: str, open_time: str, close_time: str) -> bool:
        last_entry_minutes = self._parse_time(last_entry_time)
        open_minutes = self._parse_time(open_time)
        close_minutes = self._parse_time(close_time)
        if last_entry_minutes is None or open_minutes is None or close_minutes is None:
            return False
        if close_minutes < open_minutes and last_entry_minutes < open_minutes:
            last_entry_minutes += 24 * 60
        check_minutes = minutes
        if close_minutes < open_minutes and minutes < open_minutes:
            check_minutes += 24 * 60
        return check_minutes <= last_entry_minutes

    def _minutes_in_range(self, minutes: int, start: int, end: int) -> bool:
        if end >= start:
            return start <= minutes <= end
        return minutes >= start or minutes <= end
