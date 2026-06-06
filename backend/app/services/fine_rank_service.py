import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyTag, UserProfile
from app.services.fine_rank_features import FineRankStats, build_features, build_stats


@dataclass(frozen=True)
class FineRankResult:
    poi: POI
    p_click: float
    p_like: float
    p_skip: float
    poi_relevance_score: float
    features: dict[str, Any] = field(default_factory=dict)


class FineRankService:
    """Online fine ranker backed by offline-trained sklearn models."""

    def __init__(self, model_dir: Path | None = None, interaction_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[3]
        self.model_dir = model_dir or root / "data" / "models" / "fine_rank"
        self.interaction_path = interaction_path or root / "data" / "seed" / "interaction_events.json"
        self._models = self._load_models()
        self._stats_cache: FineRankStats | None = None

    def rank(
        self,
        pois: list[POI],
        intent: Intent,
        user_profile: UserProfile,
        strategy_tags: list[StrategyTag] | None = None,
        objective: str = "balanced",
    ) -> list[FineRankResult]:
        results = [
            self.score(poi, intent, user_profile, strategy_tags=strategy_tags, objective=objective, poi_universe=pois)
            for poi in pois
        ]
        return sorted(results, key=lambda result: result.poi_relevance_score, reverse=True)

    def score(
        self,
        poi: POI,
        intent: Intent,
        user_profile: UserProfile,
        strategy_tags: list[StrategyTag] | None = None,
        objective: str = "balanced",
        poi_universe: list[POI] | None = None,
    ) -> FineRankResult:
        stats = self._stats(poi_universe or [poi])
        features = build_features(poi, intent, user_profile, strategy_tags or [], objective, stats)
        if self._models:
            p_click = self._predict_probability("click", features)
            p_like = self._predict_probability("like", features)
            p_skip = self._predict_probability("skip", features)
        else:
            p_click, p_like, p_skip = self._fallback_probabilities(features)
        p_click, p_like, p_skip = self._calibrate_probabilities(features, p_click, p_like, p_skip)
        relevance = self.relevance_score(p_click, p_like, p_skip)
        return FineRankResult(
            poi=poi,
            p_click=p_click,
            p_like=p_like,
            p_skip=p_skip,
            poi_relevance_score=relevance,
            features=features,
        )

    def score_map(
        self,
        pois: list[POI],
        intent: Intent,
        user_profile: UserProfile,
        strategy_tags: list[StrategyTag] | None = None,
        objective: str = "balanced",
    ) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
        results = self.rank(pois, intent, user_profile, strategy_tags, objective)
        scores = {result.poi.id: result.poi_relevance_score for result in results}
        details = {
            result.poi.id: {
                "p_click": result.p_click,
                "p_like": result.p_like,
                "p_skip": result.p_skip,
                "poi_relevance_score": result.poi_relevance_score,
            }
            for result in results
        }
        return scores, details

    @staticmethod
    def relevance_score(p_click: float, p_like: float, p_skip: float) -> float:
        return 0.4 * p_click + 0.5 * p_like - 0.3 * p_skip

    def _load_models(self) -> dict[str, Any]:
        paths = {
            "click": self.model_dir / "click_model.joblib",
            "like": self.model_dir / "like_model.joblib",
            "skip": self.model_dir / "skip_model.joblib",
        }
        if not all(path.exists() for path in paths.values()):
            return {}
        try:
            import joblib
        except ImportError:
            return {}
        try:
            return {name: joblib.load(path) for name, path in paths.items()}
        except (OSError, ValueError, AttributeError):
            return {}

    def _predict_probability(self, label: str, features: dict[str, Any]) -> float:
        model = self._models[label]
        probabilities = model.predict_proba([features])[0]
        classes = list(model.classes_)
        if 1 not in classes:
            return 0.0
        return self._clip(float(probabilities[classes.index(1)]))

    def _stats(self, pois: list[POI]) -> FineRankStats:
        if self._stats_cache is not None:
            return self._stats_cache
        events = self._read_events()
        poi_by_id = {poi.id: poi for poi in pois}
        self._stats_cache = build_stats(events, poi_by_id)
        return self._stats_cache

    def _read_events(self) -> list[dict[str, Any]]:
        try:
            with self.interaction_path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def _fallback_probabilities(self, features: dict[str, Any]) -> tuple[float, float, float]:
        preference = float(features.get("preference_match", 0))
        category = float(features.get("user_category_preference", 0))
        quality = min((float(features.get("poi_rating", 3)) - 3) / 2, 1)
        objective = float(features.get("objective_match", 0))
        price_ratio = float(features.get("poi_price_ratio", 1))
        queue = min(float(features.get("poi_queue_minutes", 0)) / 90, 1)
        crowd = min(float(features.get("poi_live_crowd_level", 0)), 1)
        avoid = float(features.get("avoid_match", 0))
        skipped = 1.0 if features.get("user_skipped_this_category") else 0.0
        disliked = 1.0 if features.get("user_disliked_this_poi") else 0.0

        p_click = self._clip(0.25 + preference * 0.22 + category * 0.18 + objective * 0.18 + quality * 0.14)
        p_like = self._clip(0.22 + quality * 0.25 + objective * 0.22 + float(features.get("experience_match", 0)) * 0.18)
        p_skip = self._clip(0.12 + max(price_ratio - 1, 0) * 0.22 + queue * 0.18 + crowd * 0.14 + avoid * 0.35 + skipped * 0.25 + disliked * 0.35)
        return p_click, p_like, p_skip

    def _calibrate_probabilities(self, features: dict[str, Any], p_click: float, p_like: float, p_skip: float) -> tuple[float, float, float]:
        price_ratio = float(features.get("poi_price_ratio", 1))
        budget_sensitivity = float(features.get("user_budget_sensitivity", 0.5))
        walking_tolerance = float(features.get("user_walking_tolerance", 0.5))
        crowd_tolerance = float(features.get("user_crowd_tolerance", 0.5))
        queue_minutes = float(features.get("poi_queue_minutes", 0))
        live_crowd = float(features.get("poi_live_crowd_level", 0))
        walking_intensity = str(features.get("poi_walking_intensity", "medium"))
        preference_match = float(features.get("preference_match", 0))
        objective_match = float(features.get("objective_match", 0))
        category_preference = float(features.get("user_category_preference", 0))
        avoid_match = float(features.get("avoid_match", 0))

        over_budget = max(price_ratio - 1, 0)
        if over_budget:
            p_skip += min(0.32, over_budget * budget_sensitivity * 0.28)
            p_skip = max(p_skip, min(0.95, 0.18 + over_budget * budget_sensitivity * 0.45))
            p_click -= min(0.18, over_budget * budget_sensitivity * 0.12)
        if walking_intensity == "high" and walking_tolerance < 0.35:
            p_skip += 0.18
            p_like -= 0.08
        elif walking_intensity == "low" and walking_tolerance < 0.35:
            p_skip -= 0.08
            p_like += 0.06
        if queue_minutes >= 35 and crowd_tolerance < 0.45:
            p_skip += min(0.18, queue_minutes / 240)
        if live_crowd >= 0.75 and crowd_tolerance < 0.45:
            p_skip += 0.08
        if preference_match or category_preference:
            p_click += min(0.12, preference_match * 0.08 + category_preference * 0.06)
        if objective_match:
            p_like += min(0.1, objective_match * 0.07)
        if avoid_match:
            p_skip += min(0.25, avoid_match * 0.25)
        if features.get("user_disliked_this_poi"):
            p_skip += 0.25
            p_like -= 0.12
        if features.get("user_skipped_this_category"):
            p_skip += 0.18
            p_click -= 0.08

        return self._clip(p_click), self._clip(p_like), self._clip(p_skip)

    def _clip(self, value: float) -> float:
        return max(0.0, min(1.0, value))
