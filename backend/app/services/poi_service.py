import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyTag, UserProfile
from app.services.strategy_service import StrategyService


@dataclass(frozen=True)
class POICandidate:
    poi: POI
    search_text: str
    risk_text: str


class POIService:
    """B-owned module: filters POI candidates by intent and strategy tags."""

    MIN_DEFAULT_CANDIDATES = 40

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or Path(__file__).resolve().parents[3] / "data" / "seed" / "pois.json"
        self._candidates = self._load_candidates()
        self.strategy_service = StrategyService()

    def search(self, intent: Intent, user_profile: UserProfile | None = None, limit: int = 40, strategy_tags: list[StrategyTag] | None = None) -> list[POI]:
        city_matches = [candidate for candidate in self._candidates if candidate.poi.city == intent.city]
        if not city_matches:
            city_matches = self._fallback_candidates(intent.city)
        min_candidates = min(limit, self.MIN_DEFAULT_CANDIDATES)

        strict_matches = [
            candidate
            for candidate in city_matches
            if self._matches_preferences(candidate, intent)
            and not self._matches_avoid_tags(candidate, intent)
            and self._is_not_extreme_budget_mismatch(candidate.poi, intent)
        ]
        candidates = strict_matches or [
            candidate
            for candidate in city_matches
            if not self._matches_avoid_tags(candidate, intent)
            and self._is_not_extreme_budget_mismatch(candidate.poi, intent)
        ]
        if len(candidates) < min_candidates:
            relaxed_matches = [
                candidate
                for candidate in city_matches
                if not self._matches_avoid_tags(candidate, intent)
                and self._is_not_extreme_budget_mismatch(candidate.poi, intent)
            ]
            candidates = self._merge_candidates(candidates, relaxed_matches)
        if len(candidates) < min_candidates:
            low_risk_matches = [
                candidate
                for candidate in city_matches
                if not {"long_queue", "high_price"} & set(candidate.poi.risk_flags + candidate.poi.avoid_reasons)
            ]
            candidates = self._merge_candidates(candidates, low_risk_matches)
        if not candidates:
            candidates = city_matches

        ranked = sorted(
            candidates,
            key=lambda candidate: self._rank_score(candidate, intent, user_profile, strategy_tags or []),
            reverse=True,
        )
        ranked = self._diversify_ranked_candidates(ranked, limit)
        return [candidate.poi for candidate in ranked[:limit]]

    def all_pois(self, city: str | None = None) -> list[POI]:
        pois = [candidate.poi for candidate in self._candidates]
        if city:
            return [poi for poi in pois if poi.city == city]
        return pois

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
        open_time = str(visit_info.get("open_time", "00:00"))
        close_time = str(visit_info.get("close_time", "23:59"))
        category = str(raw.get("category", ""))
        meal_type = str(planning.get("meal_type", "non_meal"))
        primary_category = str(raw.get("primary_category") or self._infer_primary_category(category, meal_type))
        secondary_categories = self._unique(
            self._as_string_list(raw.get("secondary_categories"))
            or self._infer_secondary_categories(category, tags, highlight_tags, suitability, planning, visit_info)
        )
        route_roles = self._unique(
            self._as_string_list(raw.get("route_roles"))
            or self._infer_route_roles(category, meal_type, tags, highlight_tags, primary_category, planning, suitability)
        )
        experience_tags = self._unique(
            self._as_string_list(raw.get("experience_tags"))
            or self._infer_experience_tags(tags, highlight_tags, raw.get("highlight_text", ""), raw.get("ugc_tip", ""))
        )

        poi = POI(
            id=str(raw.get("poi_id", "")),
            name=str(raw.get("name", "")),
            city=str(location.get("city", "")),
            district=str(location.get("district", "")),
            address=str(location.get("address", "")),
            category=category,
            external_place_ids=dict(raw.get("external_place_ids") or {}),
            source_provider=str(raw.get("source_provider", "local")),
            source_updated_at=str(raw.get("source_updated_at", "")),
            map_category=str(raw.get("map_category", category)),
            map_category_code=str(raw.get("map_category_code", "")),
            geohash=str(raw.get("geohash", "")),
            canonical_poi_id=str(raw.get("canonical_poi_id", raw.get("poi_id", ""))),
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            route_roles=route_roles,
            experience_tags=experience_tags,
            lat=self._to_float(location.get("lat"), 0),
            lng=self._to_float(location.get("lng"), 0),
            avg_price=avg_price,
            price_min=price_min,
            price_max=price_max,
            rating=self._to_float(quality.get("rating"), 0),
            review_count=self._to_int(quality.get("review_count"), 0),
            popularity=self._to_float(quality.get("popularity"), 0),
            crowd_level=self._to_float(quality.get("crowd_level"), 0),
            queue_minutes=self._to_int(quality.get("live_queue_time_min") or quality.get("queue_time_min"), 0),
            live_crowd_level=self._to_float(quality.get("live_crowd_level"), 0),
            visit_duration_minutes=self._to_int(visit_info.get("avg_visit_duration_min"), 60),
            open_time=open_time,
            close_time=close_time,
            last_entry_time=str(visit_info.get("last_entry_time", close_time)),
            open_hours=f"{open_time}-{close_time}",
            need_booking=bool(visit_info.get("need_booking", False)),
            suitable_time_slots=self._as_string_list(visit_info.get("suitable_time_slots")),
            tags=tags + [tag for tag in highlight_tags if tag not in tags],
            negative_tags=negative_tags,
            family_friendly=self._to_float(suitability.get("family"), 0),
            couple_friendly=self._to_float(suitability.get("couple"), 0),
            friends_friendly=self._to_float(suitability.get("friends"), 0),
            solo_friendly=self._to_float(suitability.get("solo"), 0),
            elderly_friendly=self._to_float(suitability.get("elderly"), 0),
            rainy_day_score=self._to_float(suitability.get("rainy_day"), 0),
            budget_friendly=self._to_float(suitability.get("budget_friendly"), 0),
            photo_friendly=self._to_float(suitability.get("photo_friendly"), 0),
            food_nearby=self._to_float(suitability.get("food_nearby"), 0),
            night_activity=self._to_float(suitability.get("night_activity"), 0),
            indoor=bool(planning.get("indoor", False)),
            walking_intensity=str(planning.get("walking_intensity", "medium")),
            recommended_transport=self._as_string_list(planning.get("recommended_transport")),
            nearby_poi_ids=self._as_string_list(planning.get("nearby_poi_ids")),
            risk_flags=risk_flags,
            avoid_reasons=avoid_reasons,
            meal_type=meal_type,
            transit_hub_nearby=bool(planning.get("transit_hub_nearby", False)),
            parking_available=bool(planning.get("parking_available", False)),
            cover_image_url=str(raw.get("cover_image_url", "")),
            highlight_text=str(raw.get("highlight_text", "")),
            highlight_text_tags=highlight_tags,
            ugc_tip=str(raw.get("ugc_tip", "")),
        )
        searchable_parts = [
            poi.name,
            poi.district,
            poi.address,
            poi.category,
            poi.primary_category,
            poi.highlight_text,
            poi.ugc_tip,
            poi.meal_type,
            poi.walking_intensity,
            *poi.secondary_categories,
            *poi.route_roles,
            *poi.experience_tags,
            *poi.highlight_text_tags,
            *poi.suitable_time_slots,
            *poi.recommended_transport,
            *poi.tags,
        ]
        risk_parts = [*poi.negative_tags, *poi.risk_flags, *poi.avoid_reasons, *self._as_string_list(raw.get("negative_tags"))]
        return POICandidate(
            poi=poi,
            search_text=" ".join(str(part) for part in searchable_parts if part),
            risk_text=" ".join(str(part) for part in risk_parts if part),
        )

    def _fallback_candidates(self, requested_city: str) -> list[POICandidate]:
        fallback_pool = [candidate for candidate in self._candidates if candidate.poi.city == "上海"] or self._candidates
        selected: list[POICandidate] = []
        by_category: dict[str, list[POICandidate]] = {}
        for candidate in fallback_pool:
            by_category.setdefault(candidate.poi.category, []).append(candidate)
        while len(selected) < max(self.MIN_DEFAULT_CANDIDATES, 20):
            added = False
            for candidates in by_category.values():
                if candidates:
                    selected.append(candidates.pop(0))
                    added = True
                    if len(selected) >= max(self.MIN_DEFAULT_CANDIDATES, 20):
                        break
            if not added:
                break
        return [self._clone_candidate_for_city(candidate, requested_city) for candidate in selected]

    def _clone_candidate_for_city(self, candidate: POICandidate, city: str) -> POICandidate:
        safe_city = city or "未知城市"
        poi = candidate.poi.model_copy(
            update={
                "id": f"mock_{safe_city}_{candidate.poi.id}",
                "city": safe_city,
                "source_provider": "mock_fallback",
            }
        )
        return POICandidate(poi=poi, search_text=candidate.search_text, risk_text=candidate.risk_text)

    def _merge_candidates(self, primary: list[POICandidate], secondary: list[POICandidate]) -> list[POICandidate]:
        result = list(primary)
        seen = {candidate.poi.id for candidate in result}
        for candidate in secondary:
            if candidate.poi.id in seen:
                continue
            result.append(candidate)
            seen.add(candidate.poi.id)
        return result

    def _diversify_ranked_candidates(self, ranked: list[POICandidate], limit: int) -> list[POICandidate]:
        if limit < 12 or len(ranked) <= limit:
            return ranked
        category_cap = max(4, min(10, limit // 3))
        selected: list[POICandidate] = []
        skipped: list[POICandidate] = []
        category_counts: dict[str, int] = {}
        for candidate in ranked:
            category = candidate.poi.category
            if category_counts.get(category, 0) < category_cap:
                selected.append(candidate)
                category_counts[category] = category_counts.get(category, 0) + 1
            else:
                skipped.append(candidate)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            selected.extend(candidate for candidate in skipped if candidate.poi.id not in {item.poi.id for item in selected})
        selected_ids = {candidate.poi.id for candidate in selected}
        selected.extend(candidate for candidate in ranked if candidate.poi.id not in selected_ids)
        return selected

    def _matches_budget(self, poi: POI, intent: Intent) -> bool:
        return poi.avg_price <= intent.budget_per_person

    def _is_not_extreme_budget_mismatch(self, poi: POI, intent: Intent) -> bool:
        return poi.avg_price <= max(intent.budget_per_person * 2, intent.budget_per_person + 160)

    def _matches_preferences(self, candidate: POICandidate, intent: Intent) -> bool:
        preferences = self._normalize_terms(intent.interest_tags)
        if not preferences:
            return True
        return any(self._term_matches(term, candidate.search_text) for term in preferences)

    def _matches_avoid_tags(self, candidate: POICandidate, intent: Intent) -> bool:
        avoid_tags = self._normalize_terms(intent.avoid_tags)
        return any(
            self._term_matches(term, candidate.search_text) or self._term_matches(term, candidate.risk_text)
            for term in avoid_tags
        )

    def _rank_score(
        self,
        candidate: POICandidate,
        intent: Intent,
        user_profile: UserProfile | None,
        strategy_tags: list[StrategyTag] | None = None,
    ) -> float:
        return self.coarse_rank_service.score(candidate, intent, user_profile, strategy_tags or [])

    def _profile_dimension_score(self, candidate: POICandidate, user_profile: UserProfile | None) -> float:
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

    def _scenario_score(self, candidate: POICandidate, intent: Intent) -> float:
        if intent.scenario == "friends_citywalk":
            return max(candidate.poi.friends_friendly, self._term_bonus(candidate, ["朋友", "拍照", "citywalk", "夜景", "咖啡"]))
        return 0

    def _infer_primary_category(self, category: str, meal_type: str) -> str:
        if category == "cafe" or meal_type == "cafe":
            return "cafe"
        if category in {"restaurant", "market"} or meal_type in {"local_food", "fine_dining", "light_meal", "fast_food"}:
            return "food"
        if category in {"museum", "gallery", "theater"}:
            return "culture"
        if category in {"landmark", "night_view"}:
            return "landmark"
        if category in {"park", "nature"}:
            return "nature"
        if category in {"shopping", "mall"}:
            return "shopping"
        if category in {"amusement", "entertainment"}:
            return "entertainment"
        return category or "activity"

    def _infer_secondary_categories(
        self,
        category: str,
        tags: list[str],
        highlight_tags: list[str],
        suitability: dict[str, Any],
        planning: dict[str, Any],
        visit_info: dict[str, Any],
    ) -> list[str]:
        text = " ".join([category, *tags, *highlight_tags]).lower()
        values: list[str] = []
        if any(term in text for term in ["拍照", "夜景", "经典", "文艺", "出片", "photo"]):
            values.append("photo")
        if planning.get("indoor") or any(term in text for term in ["室内", "museum", "gallery", "shopping", "cafe"]):
            values.append("indoor")
        if self._to_float(suitability.get("night_activity"), 0) >= 0.65 or {"evening", "night"} & set(self._as_string_list(visit_info.get("suitable_time_slots"))):
            values.append("night")
        if any(term in text for term in ["老字号", "本地", "市井", "本帮菜", "local"]):
            values.append("local")
        if self._to_float(suitability.get("family"), 0) >= 0.7 or any(term in text for term in ["亲子", "儿童友好"]):
            values.append("family")
        if self._to_float(suitability.get("rainy_day"), 0) >= 0.7:
            values.append("rainy")
        if any(term in text for term in ["免费", "高性价比", "budget"]):
            values.append("budget")
        return values

    def _infer_route_roles(
        self,
        category: str,
        meal_type: str,
        tags: list[str],
        highlight_tags: list[str],
        primary_category: str,
        planning: dict[str, Any],
        suitability: dict[str, Any],
    ) -> list[str]:
        text = " ".join([category, meal_type, primary_category, *tags, *highlight_tags]).lower()
        roles: list[str] = []
        if primary_category == "cafe" or meal_type == "cafe":
            roles.extend(["coffee_break", "rest_stop"])
        if primary_category == "food" and meal_type in {"local_food", "fine_dining", "fast_food"}:
            roles.append("meal")
        if primary_category == "food" and meal_type == "light_meal":
            roles.extend(["snack", "rest_stop"])
        if primary_category in {"culture", "landmark", "nature", "shopping", "entertainment"}:
            roles.append("main_activity")
        if any(term in text for term in ["拍照", "夜景", "经典", "文艺", "citywalk", "街区"]):
            roles.append("photo_stop")
        if primary_category in {"landmark", "nature"} or "citywalk" in text or "街区" in text:
            roles.append("main_activity")
        if planning.get("transit_hub_nearby") or "metro" in self._as_string_list(planning.get("recommended_transport")):
            roles.append("transit_anchor")
        if self._to_float(suitability.get("night_activity"), 0) >= 0.65:
            roles.append("night_end")
        if not roles:
            roles.append("main_activity")
        return roles

    def _infer_experience_tags(self, tags: list[str], highlight_tags: list[str], highlight_text: object, ugc_tip: object) -> list[str]:
        text = " ".join([*tags, *highlight_tags, str(highlight_text), str(ugc_tip)])
        candidates = ["老字号", "安静", "市井", "展览", "江景", "亲子", "文艺", "小众", "经典", "夜景", "本地", "雨天", "免费", "高性价比"]
        return [tag for tag in candidates if tag in text]

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
            "美食": ["美食", "吃好", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining", "food"],
            "吃好": ["美食", "吃好", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining", "food"],
            "food_first": ["美食", "吃好", "餐厅", "聚餐", "菜", "restaurant", "local_food", "fine_dining", "food"],
            "photo_food": ["拍照", "出片", "好看", "环境", "餐厅", "美食", "restaurant", "photo"],
            "nature": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "nature_relax": ["自然", "风景", "公园", "江景", "海边", "湖", "山", "森林", "nature"],
            "咖啡": ["咖啡", "下午茶", "休息", "cafe"],
            "轻食": ["轻食", "小吃", "light_meal", "fast_food", "market"],
            "小吃": ["小吃", "轻食", "light_meal", "fast_food", "market"],
            "省钱": ["省钱", "便宜", "免费", "budget"],
            "更省钱": ["省钱", "便宜", "免费", "budget"],
            "高性价比": ["高性价比", "免费", "budget"],
            "少走路": ["少走路", "轻松", "交通", "metro", "low"],
            "low_walking": ["少走路", "轻松", "交通", "metro", "low"],
            "轻松": ["少走路", "轻松", "low", "metro"],
            "citywalk": ["citywalk", "街区", "散步", "漫步", "拍照", "landmark"],
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

    def _unique(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _unique(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

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
        if any(term in {"美食", "吃好", "餐厅", "聚餐"} for term in terms):
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
