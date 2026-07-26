#!/usr/bin/env python3
"""Train real sklearn tabular models for POI fine ranking."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline

from app.schemas.intent import Intent
from app.services.fine_rank_features import FEATURE_SCHEMA_VERSION, build_features, build_stats, feature_names, label_for_event
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "seed"
MODEL_DIR = ROOT / "data" / "models" / "fine_rank"
INTERACTION_PATH = SEED_DIR / "interaction_events.json"
FEATURE_SCHEMA_PATH = MODEL_DIR / "feature_schema.json"
METADATA_PATH = MODEL_DIR / "model_metadata.json"
LABEL_TO_MODEL_PATH = {
    "click": MODEL_DIR / "click_model.joblib",
    "like": MODEL_DIR / "like_model.joblib",
    "skip": MODEL_DIR / "skip_model.joblib",
}


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    events = sorted(_read_json(INTERACTION_PATH), key=lambda item: str(item.get("timestamp", "")))
    poi_service = POIService()
    profile_service = ProfileService()
    poi_by_id = {poi.id: poi for poi in poi_service.all_pois()}
    events, hard_negative_count = _augment_hard_negatives(events, poi_by_id)
    events.sort(key=lambda item: str(item.get("timestamp", "")))
    stats = build_stats(events, poi_by_id)

    features: list[dict[str, Any]] = []
    labels = {"click": [], "like": [], "skip": []}
    missing_users = 0
    missing_pois = 0
    for event in events:
        poi = poi_by_id.get(str(event.get("poi_id", "")))
        if poi is None:
            missing_pois += 1
            continue
        profile = profile_service.get_seed_profile(str(event.get("user_id", "")))
        if profile is None:
            missing_users += 1
            continue
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        intent = Intent(
            city=str(event.get("city") or poi.city),
            budget_per_person=int(context.get("budget_per_person") or 300),
            preferences=[str(item) for item in context.get("preferences", []) if item],
            scenario=str(context.get("scenario") or "friends_citywalk"),
            start_time=_start_time_from_slot(str(context.get("time_slot") or "afternoon")),
        )
        objective = str(context.get("route_objective") or "balanced")
        row = build_features(poi, intent, profile, strategy_tags=[], objective=objective, stats=stats, event_context=context)
        features.append(row)
        event_labels = label_for_event(str(event.get("event_type", "")))
        for label, value in event_labels.items():
            labels[label].append(value)

    if not features:
        raise RuntimeError("No valid fine-rank training samples were built.")

    metrics: dict[str, dict[str, float | int]] = {}
    vectorized_feature_names: dict[str, list[str]] = {}
    for label, y in labels.items():
        if len(set(y)) < 2:
            raise RuntimeError(f"Label {label} needs both positive and negative samples.")
        model, label_metrics, feature_names_for_label = _train_label_model(features, y)
        joblib.dump(model, LABEL_TO_MODEL_PATH[label])
        metrics[label] = label_metrics
        vectorized_feature_names[label] = feature_names_for_label

    schema = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "raw_features": feature_names(features),
        "vectorized_features": vectorized_feature_names,
    }
    _write_json(FEATURE_SCHEMA_PATH, schema)
    metadata = {
        "model_type": "DictVectorizer+LogisticRegression",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(features),
        "hard_negative_count": hard_negative_count,
        "split_strategy": "chronological_80_20",
        "missing_users": missing_users,
        "missing_pois": missing_pois,
        "label_positive_rates": {label: round(sum(values) / len(values), 6) for label, values in labels.items()},
        "metrics": metrics,
    }
    _write_json(METADATA_PATH, metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


def _train_label_model(features: list[dict[str, Any]], labels: list[int]) -> tuple[Pipeline, dict[str, float | int], list[str]]:
    split_index = max(1, round(len(features) * 0.8))
    train_idx = list(range(split_index))
    test_idx = list(range(split_index, len(features)))
    x_train = [features[index] for index in train_idx]
    x_test = [features[index] for index in test_idx]
    y_train = [labels[index] for index in train_idx]
    y_test = [labels[index] for index in test_idx]
    model = Pipeline(
        steps=[
            ("vectorizer", DictVectorizer(sparse=True)),
            ("classifier", LogisticRegression(max_iter=800, class_weight="balanced", solver="liblinear", random_state=20260604)),
        ]
    )
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, list(model.classes_).index(1)]
    predictions = model.predict(x_test)
    metrics = {
        "train_samples": len(x_train),
        "test_samples": len(x_test),
        "accuracy": round(float(accuracy_score(y_test, predictions)), 6),
        "auc": round(float(roc_auc_score(y_test, probabilities)), 6),
        "brier_score": round(float(brier_score_loss(y_test, probabilities)), 6),
        "calibration_error": round(_expected_calibration_error(y_test, probabilities), 6),
    }
    vectorizer = model.named_steps["vectorizer"]
    return model, metrics, list(vectorizer.get_feature_names_out())


def _augment_hard_negatives(events: list[dict[str, Any]], poi_by_id: dict[str, Any], limit: int = 2000) -> tuple[list[dict[str, Any]], int]:
    by_city: dict[str, list[Any]] = {}
    for poi in poi_by_id.values():
        by_city.setdefault(poi.city, []).append(poi)
    augmented = list(events)
    added = 0
    positive_types = {"click", "save", "like", "selected_in_route", "completed_visit"}
    for index, event in enumerate(events):
        if added >= limit or index % 8 or str(event.get("event_type")) not in positive_types:
            continue
        context = event.get("context") if isinstance(event.get("context"), dict) else {}
        budget = int(context.get("budget_per_person") or 300)
        original = poi_by_id.get(str(event.get("poi_id", "")))
        if original is None:
            continue
        candidates = by_city.get(original.city, [])
        hard = next(
            (
                poi
                for poi in candidates
                if poi.id != original.id
                and poi.primary_category == original.primary_category
                and (poi.avg_price > max(budget * 1.5, budget + 120) or poi.walking_intensity == "high" or poi.queue_minutes >= 45)
            ),
            None,
        )
        if hard is None:
            continue
        synthetic = dict(event)
        synthetic["event_id"] = f"hardneg_{event.get('event_id', index)}"
        synthetic["poi_id"] = hard.id
        synthetic["event_type"] = "skip"
        synthetic["event_value"] = -1.0
        synthetic["hard_negative"] = True
        augmented.append(synthetic)
        added += 1
    return augmented, added


def _expected_calibration_error(labels: list[int], probabilities: Any, bins: int = 10) -> float:
    total = max(len(labels), 1)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [position for position, probability in enumerate(probabilities) if lower <= probability < upper or (index == bins - 1 and probability == 1)]
        if not bucket:
            continue
        confidence = sum(float(probabilities[position]) for position in bucket) / len(bucket)
        accuracy = sum(labels[position] for position in bucket) / len(bucket)
        error += len(bucket) / total * abs(confidence - accuracy)
    return error


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _start_time_from_slot(slot: str) -> str:
    return {
        "morning": "09:00",
        "afternoon": "14:00",
        "evening": "19:00",
        "night": "21:00",
    }.get(slot, "14:00")


if __name__ == "__main__":
    main()
