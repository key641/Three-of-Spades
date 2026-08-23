from __future__ import annotations

import json
import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.schemas.intent import Intent
from app.schemas.user import StrategyTag, UserProfile


@dataclass(frozen=True)
class RecallContext:
    intent: Intent
    user_profile: UserProfile | None
    strategy_tags: list[StrategyTag]
    candidates: list[Any]
    target_pool_size: int


@dataclass
class RecallResult:
    candidate: Any
    channel: str
    reason: str
    score_hint: float = 0.0
    channels: set[str] = field(default_factory=set)


class RecallService:
    """Multi-channel recall layer before temporary coarse ranking."""

    CHANNEL_LIMITS = {
        "content": 80,
        "profile": 80,
        "collaborative_filtering": 120,
        "two_tower": 160,
        "scenario": 80,
        "route_role": 80,
    }

    REQUIRED_ROLES = ["main_activity", "meal", "rest_stop", "coffee_break", "photo_stop", "transit_anchor", "night_end"]
    RRF_K = 60
    CHANNEL_WEIGHTS = {
        "content": 1.0,
        "profile": 1.0,
        "collaborative_filtering": 0.9,
        "two_tower": 1.0,
        "scenario": 1.1,
        "route_role": 1.1,
    }

    def __init__(
        self,
        interaction_path: Path | None = None,
        poi_embedding_path: Path | None = None,
        user_embedding_path: Path | None = None,
        item_similarity_path: Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[3]
        self.interaction_path = interaction_path or root / "data" / "seed" / "interaction_events.json"
        self.poi_embedding_path = poi_embedding_path or root / "data" / "models" / "two_tower" / "poi_embeddings.json"
        self.user_embedding_path = user_embedding_path or root / "data" / "models" / "two_tower" / "user_embeddings.json"
        self.item_similarity_path = item_similarity_path or root / "data" / "models" / "cf" / "item_similarity.json"
        self._events = self._load_json(self.interaction_path, [])
        self._poi_embeddings = self._load_json(self.poi_embedding_path, {}).get("embeddings", {})
        self._user_embeddings = self._load_json(self.user_embedding_path, {}).get("embeddings", {})
        self._item_similarity = self._load_json(self.item_similarity_path, {}).get("items", {})
        self._events_by_user = self._index_events_by_user(self._events)
        self.last_diagnostics: dict[str, Any] = {}

    def recall(
        self,
        intent: Intent,
        candidates: list[Any],
        user_profile: UserProfile | None = None,
        strategy_tags: list[StrategyTag] | None = None,
        target_pool_size: int = 240,
    ) -> list[Any]:
        context = RecallContext(
            intent=intent,
            user_profile=user_profile,
            strategy_tags=strategy_tags or [],
            candidates=candidates,
            target_pool_size=target_pool_size,
        )
        channel_results = {
            "content": self._content_recall(context, self.CHANNEL_LIMITS["content"]),
            "scenario": self._scenario_recall(context, self.CHANNEL_LIMITS["scenario"]),
            "route_role": self._route_role_recall(context, self.CHANNEL_LIMITS["route_role"]),
        }
        if user_profile is not None:
            channel_results["profile"] = self._profile_recall(context, self.CHANNEL_LIMITS["profile"])
            channel_results["collaborative_filtering"] = self._collaborative_recall(
                context, self.CHANNEL_LIMITS["collaborative_filtering"]
            )
        channel_results["two_tower"] = self._two_tower_recall(context, self.CHANNEL_LIMITS["two_tower"])
        merged = self._rrf_merge(channel_results)
        diversified = self._diversify(merged, context.target_pool_size)
        if len(diversified) < context.target_pool_size:
            diversified = self._append_fallback(diversified, context.candidates, context.target_pool_size)
        self.last_diagnostics = {
            "input_count": len(candidates),
            "target_pool_size": target_pool_size,
            "channel_counts": {channel: len(items) for channel, items in channel_results.items()},
            "merged_count": len(merged),
            "output_count": min(len(diversified), context.target_pool_size),
            "fusion": "weighted_rrf",
        }
        return [result.candidate for result in diversified[: context.target_pool_size]]

    def _rrf_merge(self, channel_results: dict[str, list[RecallResult]]) -> list[RecallResult]:
        merged: dict[str, RecallResult] = {}
        for channel, results in channel_results.items():
            weight = self.CHANNEL_WEIGHTS.get(channel, 1.0)
            for rank, result in enumerate(results, start=1):
                poi_id = result.candidate.poi.id
                rrf_score = weight / (self.RRF_K + rank)
                if poi_id not in merged:
                    merged[poi_id] = RecallResult(
                        candidate=result.candidate,
                        channel=channel,
                        reason=result.reason,
                        score_hint=rrf_score,
                        channels={channel},
                    )
                else:
                    merged[poi_id].score_hint += rrf_score
                    merged[poi_id].channels.add(channel)
                    merged[poi_id].reason = "+".join(sorted(merged[poi_id].channels))
        return sorted(
            merged.values(),
            key=lambda item: (item.score_hint, len(item.channels)),
            reverse=True,
        )

    def _content_recall(self, context: RecallContext, limit: int) -> list[RecallResult]:
        terms = self._terms([*context.intent.preferences, *(tag.tag for tag in context.strategy_tags), context.intent.scenario])
        if not terms:
            return []
        results = []
        for candidate in context.candidates:
            text = self._candidate_text(candidate)
            score = sum(1 for term in terms if self._term_matches(term, text))
            if score:
                results.append(RecallResult(candidate, "content", "偏好/文本命中", score))
        return sorted(results, key=lambda item: item.score_hint, reverse=True)[:limit]

    def _profile_recall(self, context: RecallContext, limit: int) -> list[RecallResult]:
        profile = context.user_profile
        if profile is None:
            return []
        results = []
        for candidate in context.candidates:
            poi = candidate.poi
            score = 0.0
            score += max(
                profile.category_preferences.get(poi.category, 0),
                profile.category_preferences.get(poi.primary_category, 0),
                *(profile.category_preferences.get(category, 0) for category in poi.secondary_categories),
            )
            score += len(set(profile.preferred_route_roles) & set(poi.route_roles)) * 0.35
            score += len(set(profile.preferred_experience_tags) & set(poi.experience_tags + poi.tags + poi.highlight_text_tags)) * 0.25
            score += len(set(profile.preferred_time_slots) & set(poi.suitable_time_slots)) * 0.2
            score += len(set(profile.preferred_transport_modes) & set(poi.recommended_transport)) * 0.15
            if poi.id in profile.liked_poi_ids:
                score += 1.2
            if poi.id in profile.disliked_poi_ids or poi.category in profile.skipped_categories:
                score -= 1.0
            if score > 0:
                results.append(RecallResult(candidate, "profile", "画像特征命中", score))
        return sorted(results, key=lambda item: item.score_hint, reverse=True)[:limit]

    def _collaborative_recall(self, context: RecallContext, limit: int) -> list[RecallResult]:
        profile = context.user_profile
        if profile is None:
            return []
        candidate_by_id = {candidate.poi.id: candidate for candidate in context.candidates}
        positive_ids = set(profile.liked_poi_ids)
        negative_ids = set(profile.disliked_poi_ids)
        for event in self._events_by_user.get(profile.user_id, []):
            if float(event.get("event_value", 0)) > 0:
                positive_ids.add(str(event.get("poi_id")))
            elif float(event.get("event_value", 0)) < 0:
                negative_ids.add(str(event.get("poi_id")))
        if not positive_ids:
            return []

        scores: dict[str, float] = {}
        for poi_id in positive_ids:
            for item in self._item_similarity.get(poi_id, [])[:30]:
                candidate_id = str(item.get("poi_id"))
                if candidate_id in negative_ids or candidate_id in positive_ids:
                    continue
                if candidate_id in candidate_by_id:
                    scores[candidate_id] = scores.get(candidate_id, 0) + float(item.get("score", 0))
        for poi_id in negative_ids:
            for item in self._item_similarity.get(poi_id, [])[:20]:
                candidate_id = str(item.get("poi_id"))
                if candidate_id in scores:
                    scores[candidate_id] -= float(item.get("score", 0)) * 1.5

        results = [
            RecallResult(candidate_by_id[poi_id], "collaborative_filtering", "相似用户/相似 POI 召回", score)
            for poi_id, score in scores.items()
            if score > 0
        ]
        return sorted(results, key=lambda item: item.score_hint, reverse=True)[:limit]

    def _two_tower_recall(self, context: RecallContext, limit: int) -> list[RecallResult]:
        if not self._poi_embeddings:
            return []
        user_vector = self._user_embedding(context)
        if not user_vector:
            return []
        results = []
        for candidate in context.candidates:
            vector = self._poi_embeddings.get(candidate.poi.id)
            if not vector:
                continue
            score = self._dot(user_vector, vector)
            if score > 0:
                results.append(RecallResult(candidate, "two_tower", "双塔 embedding 相似召回", score))
        return sorted(results, key=lambda item: item.score_hint, reverse=True)[:limit]

    def _scenario_recall(self, context: RecallContext, limit: int) -> list[RecallResult]:
        terms = set(context.intent.preferences + [tag.tag for tag in context.strategy_tags] + [context.intent.scenario])
        results = []
        for candidate in context.candidates:
            poi = candidate.poi
            score = 0.0
            if self._has_any(terms, {"室内", "雨天", "indoor_rainy"}) and (poi.indoor or poi.rainy_day_score >= 0.7):
                score += 1.0
            if self._has_any(terms, {"晚上", "夜景", "night_view", "night_friendly"}) and (poi.night_activity >= 0.7 or "night" in poi.suitable_time_slots):
                score += 1.0
            if self._has_any(terms, {"少走路", "轻松", "low_walking"}) and (poi.walking_intensity == "low" or "transit_anchor" in poi.route_roles):
                score += 1.0
            if self._has_any(terms, {"吃好", "咖啡", "food_first"}) and (poi.meal_type != "non_meal" or poi.category in {"restaurant", "cafe", "market"}):
                score += 1.0
            if self._has_any(terms, {"拍照", "citywalk", "photo_citywalk"}) and ("photo_stop" in poi.route_roles or poi.photo_friendly >= 0.7):
                score += 1.0
            if self._has_any(terms, {"自然", "自然风景", "nature_relax"}) and (poi.category == "park" or poi.primary_category == "nature"):
                score += 1.0
            if score > 0:
                results.append(RecallResult(candidate, "scenario", "场景召回", score))
        return sorted(results, key=lambda item: item.score_hint, reverse=True)[:limit]

    def _route_role_recall(self, context: RecallContext, limit: int) -> list[RecallResult]:
        results = []
        per_role_limit = max(4, limit // max(len(self.REQUIRED_ROLES), 1))
        for role in self.REQUIRED_ROLES:
            role_candidates = [
                RecallResult(candidate, "route_role", f"路线角色 {role} 覆盖", 1.0)
                for candidate in context.candidates
                if role in candidate.poi.route_roles
            ]
            results.extend(role_candidates[:per_role_limit])
        return results[:limit]

    def _merge_results(self, results: list[RecallResult]) -> list[RecallResult]:
        merged: dict[str, RecallResult] = {}
        for result in results:
            poi_id = result.candidate.poi.id
            if poi_id not in merged:
                result.channels = {result.channel}
                merged[poi_id] = result
                continue
            existing = merged[poi_id]
            existing.score_hint += result.score_hint
            existing.channels.add(result.channel)
            existing.reason = "+".join(sorted(existing.channels))
        return sorted(merged.values(), key=lambda item: (len(item.channels), item.score_hint), reverse=True)

    def _diversify(self, results: list[RecallResult], target: int) -> list[RecallResult]:
        if not results:
            return []
        category_cap = max(8, math.ceil(target * 0.25))
        primary_cap = max(12, math.ceil(target * 0.35))
        selected: list[RecallResult] = []
        category_counts: dict[str, int] = {}
        primary_counts: dict[str, int] = {}

        def add(result: RecallResult) -> bool:
            poi = result.candidate.poi
            if result in selected:
                return False
            if category_counts.get(poi.category, 0) >= category_cap:
                return False
            if primary_counts.get(poi.primary_category, 0) >= primary_cap:
                return False
            selected.append(result)
            category_counts[poi.category] = category_counts.get(poi.category, 0) + 1
            primary_counts[poi.primary_category] = primary_counts.get(poi.primary_category, 0) + 1
            return True

        for role in self.REQUIRED_ROLES:
            role_result = next((result for result in results if role in result.candidate.poi.route_roles), None)
            if role_result:
                add(role_result)
        for result in results:
            if len(selected) >= target:
                break
            add(result)
        if len(selected) < target:
            selected_ids = {result.candidate.poi.id for result in selected}
            selected.extend(result for result in results if result.candidate.poi.id not in selected_ids)
        return selected[:target]

    def _append_fallback(self, selected: list[RecallResult], candidates: list[Any], target: int) -> list[RecallResult]:
        seen = {result.candidate.poi.id for result in selected}
        category_counts = {result.candidate.poi.category: 0 for result in selected}
        for result in selected:
            category_counts[result.candidate.poi.category] = category_counts.get(result.candidate.poi.category, 0) + 1
        for candidate in candidates:
            if len(selected) >= target:
                break
            if candidate.poi.id in seen:
                continue
            if category_counts.get(candidate.poi.category, 0) > max(8, target // 4):
                continue
            selected.append(RecallResult(candidate, "fallback", "多样性兜底", 0))
            seen.add(candidate.poi.id)
            category_counts[candidate.poi.category] = category_counts.get(candidate.poi.category, 0) + 1
        if len(selected) < target:
            for candidate in candidates:
                if len(selected) >= target:
                    break
                if candidate.poi.id not in seen:
                    selected.append(RecallResult(candidate, "fallback", "数量兜底", 0))
                    seen.add(candidate.poi.id)
        return selected

    def _user_embedding(self, context: RecallContext) -> list[float] | None:
        profile = context.user_profile
        if profile and profile.user_id in self._user_embeddings:
            return self._user_embeddings[profile.user_id]
        terms = context.intent.preferences + [tag.tag for tag in context.strategy_tags]
        vector = [0.0] * 64
        for term in terms:
            index = self._stable_bucket(term, len(vector))
            vector[index] += 1
        if profile:
            for category, score in profile.category_preferences.items():
                vector[self._stable_bucket(f"category:{category}", len(vector))] += float(score)
            vector[0] += profile.budget_sensitivity
            vector[1] += profile.walking_tolerance
            vector[2] += profile.crowd_tolerance
            vector[3] += profile.novelty_preference
            vector[4] += profile.comfort_preference
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            return None
        return [value / norm for value in vector]

    def _stable_bucket(self, value: str, size: int) -> int:
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") % size

    def _candidate_text(self, candidate: Any) -> str:
        poi = candidate.poi
        return " ".join(
            str(part)
            for part in [
                getattr(candidate, "search_text", ""),
                poi.name,
                poi.category,
                poi.primary_category,
                poi.meal_type,
                poi.highlight_text,
                poi.ugc_tip,
                *poi.secondary_categories,
                *poi.route_roles,
                *poi.experience_tags,
                *poi.tags,
                *poi.highlight_text_tags,
                *poi.suitable_time_slots,
            ]
            if part
        ).lower()

    def _term_matches(self, term: str, text: str) -> bool:
        aliases = {
            "吃好": ["吃好", "美食", "餐厅", "restaurant", "meal"],
            "咖啡": ["咖啡", "cafe", "coffee_break"],
            "拍照": ["拍照", "出片", "photo", "photo_stop"],
            "citywalk": ["citywalk", "街区", "散步", "landmark"],
            "室内": ["室内", "雨天", "indoor", "museum", "gallery", "shopping"],
            "雨天": ["雨天", "室内", "rainy"],
            "少走路": ["少走路", "轻松", "low", "metro", "transit_anchor"],
            "晚上": ["晚上", "夜景", "night", "night_end"],
            "夜景": ["晚上", "夜景", "night", "night_end"],
            "自然": ["自然", "风景", "公园", "nature", "park"],
            "自然风景": ["自然", "风景", "公园", "nature", "park"],
        }
        return any(value.lower() in text for value in aliases.get(term, [term]))

    def _terms(self, values: list[str]) -> list[str]:
        result = []
        for value in values:
            normalized = str(value).strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    def _has_any(self, terms: set[str], values: set[str]) -> bool:
        return any(value in term or term in value for term in terms for value in values)

    def _dot(self, left: list[float], right: list[float]) -> float:
        return sum(float(a) * float(b) for a, b in zip(left, right))

    def _load_json(self, path: Path, default: Any) -> Any:
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return default

    def _index_events_by_user(self, events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        indexed: dict[str, list[dict[str, Any]]] = {}
        for event in events:
            indexed.setdefault(str(event.get("user_id")), []).append(event)
        return indexed
