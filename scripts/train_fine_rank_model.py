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
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
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
    events = _read_json(INTERACTION_PATH)
    poi_service = POIService()
    profile_service = ProfileService()
    poi_by_id = {poi.id: poi for poi in poi_service.all_pois()}
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
        "missing_users": missing_users,
        "missing_pois": missing_pois,
        "label_positive_rates": {label: round(sum(values) / len(values), 6) for label, values in labels.items()},
        "metrics": metrics,
    }
    _write_json(METADATA_PATH, metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


def _train_label_model(features: list[dict[str, Any]], labels: list[int]) -> tuple[Pipeline, dict[str, float | int], list[str]]:
    indices = list(range(len(features)))
    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=20260604, stratify=labels)
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
    }
    vectorizer = model.named_steps["vectorizer"]
    return model, metrics, list(vectorizer.get_feature_names_out())


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
