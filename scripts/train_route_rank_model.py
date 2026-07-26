#!/usr/bin/env python3
"""Train a route-level selector only after real-signal admission gates pass."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "runtime" / "route_signals.db")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "models" / "route_rank")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    rows, counts = _load_rows(args.db)
    gate_failures = _data_gate_failures(counts)
    if gate_failures and not args.force:
        print(json.dumps({"trained": False, "counts": counts, "gate_failures": gate_failures}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    if len({label for _features, label, _request_id, _created_at in rows}) < 2:
        raise SystemExit("route signals contain only one label; training is unsafe")
    rows.sort(key=lambda row: row[3])
    split = max(1, round(len(rows) * 0.8))
    train, test = rows[:split], rows[split:]
    model = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=True)),
            ("classifier", LogisticRegression(max_iter=800, class_weight="balanced", solver="liblinear", random_state=20260721)),
        ]
    )
    model.fit([row[0] for row in train], [row[1] for row in train])
    probabilities = model.predict_proba([row[0] for row in test])[:, list(model.classes_).index(1)]
    labels = [row[1] for row in test]
    model_ndcg = _mean_ndcg(test, probabilities)
    baseline_ndcg = _mean_ndcg(test, [-float(row[0].get("position", 99)) for row in test])
    metrics = {
        "auc": round(float(roc_auc_score(labels, probabilities)), 6),
        "brier_score": round(float(brier_score_loss(labels, probabilities)), 6),
        "calibration_error": round(_ece(labels, probabilities), 6),
        "ndcg": round(model_ndcg, 6),
        "baseline_ndcg": round(baseline_ndcg, 6),
    }
    admitted = metrics["auc"] >= 0.55 and metrics["calibration_error"] <= 0.15 and model_ndcg > baseline_ndcg
    metadata = {
        "trained": True,
        "admitted": admitted,
        "counts": counts,
        "split_strategy": "chronological_80_20",
        "train_samples": len(train),
        "test_samples": len(test),
        "metrics": metrics,
        "trained_at": datetime.utcnow().isoformat() + "Z",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.output_dir / "route_rank_model.joblib")
    (args.output_dir / "model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    if not admitted:
        raise SystemExit(1)


def _load_rows(db_path: Path) -> tuple[list[tuple[dict[str, Any], int, str, str]], dict[str, Any]]:
    if not db_path.exists():
        return [], {"impressions": 0, "selections": 0, "day_span": 0}
    with sqlite3.connect(str(db_path)) as connection:
        impressions = connection.execute(
            "SELECT request_id,session_id,route_id,position,payload_json,created_at FROM route_events WHERE event_kind='impression' ORDER BY created_at"
        ).fetchall()
        positives = {
            (row[0], row[1])
            for row in connection.execute(
                "SELECT session_id,route_id FROM route_events WHERE event_kind='feedback' AND event_type IN ('route_selected','selected','route_feedback')"
            )
        }
    rows: list[tuple[dict[str, Any], int, str, str]] = []
    for request_id, session_id, route_id, position, payload_json, created_at in impressions:
        payload = json.loads(payload_json)
        route = payload.get("route", {})
        features = {
            "position": int(position or 0),
            "objective": str(payload.get("objective", "balanced")),
            "score": float(payload.get("score", 0)),
            "stop_count": len(route.get("stops", [])),
            "duration": float(route.get("total_duration_minutes", 0)),
            "cost": float(route.get("total_cost_per_person", 0)),
            "travel": float(route.get("total_travel_minutes", 0)),
            "reliability": float(route.get("reliability_score", 0)),
            "degradation_level": int(route.get("degradation_level", 0)),
        }
        rows.append((features, int((session_id, route_id) in positives), request_id, created_at))
    dates = [datetime.fromisoformat(row[5].replace("Z", "+00:00")) for row in impressions]
    day_span = (max(dates) - min(dates)).days + 1 if dates else 0
    return rows, {"impressions": len(impressions), "selections": len(positives), "day_span": day_span}


def _data_gate_failures(counts: dict[str, Any]) -> list[str]:
    checks = [(counts["impressions"] >= 10000, "impressions<10000"), (counts["selections"] >= 1000, "selections<1000"), (counts["day_span"] >= 7, "day_span<7")]
    return [message for passed, message in checks if not passed]


def _mean_ndcg(rows: list[tuple[dict[str, Any], int, str, str]], scores: Any) -> float:
    groups: dict[str, list[tuple[float, int]]] = {}
    for row, score in zip(rows, scores):
        groups.setdefault(row[2], []).append((float(score), row[1]))
    values: list[float] = []
    for items in groups.values():
        ranked = sorted(items, reverse=True)
        dcg = sum(label / math.log2(index + 2) for index, (_score, label) in enumerate(ranked))
        ideal = sum(label / math.log2(index + 2) for index, label in enumerate(sorted((label for _score, label in items), reverse=True)))
        values.append(dcg / ideal if ideal else 0.0)
    return sum(values) / max(len(values), 1)


def _ece(labels: list[int], probabilities: Any, bins: int = 10) -> float:
    error = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        bucket = [i for i, value in enumerate(probabilities) if lower <= value < upper or (index == bins - 1 and value == 1)]
        if bucket:
            confidence = sum(float(probabilities[i]) for i in bucket) / len(bucket)
            accuracy = sum(labels[i] for i in bucket) / len(bucket)
            error += len(bucket) / max(len(labels), 1) * abs(confidence - accuracy)
    return error


if __name__ == "__main__":
    main()
