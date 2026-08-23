#!/usr/bin/env python3
"""Deterministic route-strategy evaluation, ablation, reporting, and release gates."""

from __future__ import annotations

import argparse
import json
import math
import platform
import random
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas.intent import Intent
from app.schemas.route import Route, RoutePlanRequest
from app.services.constraint_evaluator import ConstraintEvaluator
from app.services.fine_rank_service import FineRankService
from app.services.planning_experiment import PlanningExperimentConfig
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService
from app.services.strategy_service import StrategyService


SCENARIOS = [
    ("photo_citywalk", ["citywalk", "拍照"], [], 3, 250),
    ("food", ["吃好"], ["排队久"], 5, 300),
    ("coffee_bookstore", ["咖啡", "书店"], [], 3, 180),
    ("low_walking", ["少走路", "轻松"], [], 5, 300),
    ("rainy_indoor", ["雨天", "室内"], [], 5, 300),
    ("night_required", ["晚上", "夜景"], [], 4, 300),
    ("budget", ["省钱", "高性价比"], [], 6, 150),
    ("nature", ["自然风景"], [], 5, 250),
    ("family", ["亲子", "室内"], [], 5, 350),
    ("senior", ["老人", "少走路"], [], 4, 300),
    ("food_crawl", ["美食路线", "扫街"], [], 6, 350),
    ("gallery_required", ["艺术展", "拍照"], [], 5, 300),
]


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    scenario: str
    intent: Intent


EXPERIMENTS = {
    "v2": PlanningExperimentConfig(),
    "legacy_recall": PlanningExperimentConfig(recall_mode="legacy"),
    "balanced_rank": PlanningExperimentConfig(fine_rank_mode="balanced"),
    "greedy": PlanningExperimentConfig(search_mode="greedy"),
    "zero_overlap": PlanningExperimentConfig(diversity_mode="zero_overlap"),
    "no_rerank": PlanningExperimentConfig(route_rerank_enabled=False),
    "baseline": PlanningExperimentConfig.baseline(),
}


def build_cases(poi_service: POIService) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for city in ["上海", "北京"]:
        city_pois = poi_service.all_pois(city)
        for repeat in range(5):
            for index, (scenario, preferences, avoid_tags, hours, budget) in enumerate(SCENARIOS):
                must_category = {5: "night_view", 11: "gallery"}.get(index)
                matching_required = [poi for poi in city_pois if poi.category == must_category]
                if must_category == "night_view":
                    center = RouteService.CITY_CENTERS[city]
                    matching_required = [
                        poi
                        for poi in matching_required
                        if poi.visit_duration_minutes <= 90
                        and poi.queue_minutes <= 20
                        and poi.visit_duration_minutes + poi.queue_minutes <= 90
                        and _distance_km(center[0], center[1], poi.lat, poi.lng) <= 8
                        and sum(
                            other.id != poi.id
                            and other.category == "night_view"
                            and other.visit_duration_minutes + other.queue_minutes <= 90
                            and _distance_km(poi.lat, poi.lng, other.lat, other.lng) <= 4
                            for other in city_pois
                        ) >= 4
                    ]
                must_include = [matching_required[repeat % len(matching_required)].id] if matching_required else []
                cases.append(
                    EvaluationCase(
                        case_id=f"{city}_{repeat}_{index}",
                        scenario=scenario,
                        intent=Intent(
                            city=city,
                            preferences=list(preferences),
                            avoid_tags=list(avoid_tags),
                            duration_hours=hours,
                            budget_per_person=budget,
                            must_include_poi_ids=must_include,
                        ),
                    )
                )
    return cases


def evaluate(
    candidate_limit: int | None = None,
    max_cases: int | None = None,
    experiment: PlanningExperimentConfig | None = None,
    seed: int = 20260721,
) -> dict[str, Any]:
    random.seed(seed)
    experiment = experiment or PlanningExperimentConfig()
    previous_mode = settings.planning_pipeline_mode
    previous_rollout = settings.planning_pipeline_rollout_percent
    settings.planning_pipeline_mode = "legacy" if experiment.recall_mode == "legacy" else "v2"
    settings.planning_pipeline_rollout_percent = 100
    try:
        return _evaluate(candidate_limit, max_cases, experiment, seed)
    finally:
        settings.planning_pipeline_mode = previous_mode
        settings.planning_pipeline_rollout_percent = previous_rollout


def _evaluate(
    candidate_limit: int | None,
    max_cases: int | None,
    experiment: PlanningExperimentConfig,
    seed: int,
) -> dict[str, Any]:
    poi_service = POIService()
    profile_service = ProfileService()
    fine_rank_service = FineRankService()
    route_service = RouteService(experiment_config=experiment)
    strategy_service = StrategyService()
    constraints = ConstraintEvaluator()
    cases = build_cases(poi_service)
    if max_cases is not None:
        cases = cases[:max_cases]
    latencies: list[float] = []
    route_success = three_route_success = hard_violations = required_hits = required_total = 0
    required_route_missing = role_covered = role_expected = 0
    overlaps: list[float] = []
    case_results: list[dict[str, Any]] = []

    for case in cases:
        started = time.perf_counter()
        profile = profile_service.get_profile("user_demo")
        tags = strategy_service.infer_tags(" ".join(case.intent.preferences), case.intent, profile)
        weights = profile_service.build_strategy_weights(case.intent, profile, tags)
        recall_started = time.perf_counter()
        pois = poi_service.search(case.intent, profile, limit=candidate_limit, strategy_tags=tags)
        recall_ms = (time.perf_counter() - recall_started) * 1000
        poi_ids = {poi.id for poi in pois}
        required_total += len(case.intent.must_include_poi_ids)
        required_hits += len(set(case.intent.must_include_poi_ids) & poi_ids)

        request = RoutePlanRequest(
            intent=case.intent,
            user_profile=profile,
            strategy_weights=weights,
            strategy_tags=tags,
            candidate_pois=pois,
            debug=True,
        )
        objectives = route_service.planning_objectives(request)
        fine_started = time.perf_counter()
        if experiment.fine_rank_mode == "balanced":
            scores, details = fine_rank_service.score_map(pois, case.intent, profile, tags, "balanced")
            request.poi_relevance_scores_by_objective = {objective: scores for objective in objectives}
            request.poi_fine_rank_details_by_objective = {objective: details for objective in objectives}
        else:
            for objective in objectives:
                scores, details = fine_rank_service.score_map(pois, case.intent, profile, tags, objective)
                request.poi_relevance_scores_by_objective[objective] = scores
                request.poi_fine_rank_details_by_objective[objective] = details
        request.poi_relevance_scores = request.poi_relevance_scores_by_objective.get("balanced", {})
        fine_ms = (time.perf_counter() - fine_started) * 1000
        route_started = time.perf_counter()
        response = route_service.generate_routes(request)
        route_ms = (time.perf_counter() - route_started) * 1000
        total_ms = (time.perf_counter() - started) * 1000
        latencies.append(total_ms)

        route_success += bool(response.routes)
        three_route_success += len(response.routes) >= 3
        poi_by_id = {poi.id: poi for poi in pois}
        case_hard = 0
        for route in response.routes:
            violations = constraints.evaluate_route(route, request, poi_by_id).hard_violations
            hard_violations += len(violations)
            case_hard += len(violations)
            if not set(case.intent.must_include_poi_ids) <= {stop.poi_id for stop in route.stops}:
                required_route_missing += 1
            if "吃好" in case.intent.preferences or "美食路线" in case.intent.preferences:
                role_expected += 1
                role_covered += any({"meal", "snack"} & set(stop.route_roles) for stop in route.stops)
            role_expected += 1
            role_covered += any("main_activity" in stop.route_roles for stop in route.stops)
        case_overlaps = _pairwise_overlaps(response.routes, set(case.intent.must_include_poi_ids))
        overlaps.extend(case_overlaps)
        case_results.append(
            {
                "case_id": case.case_id,
                "city": case.intent.city,
                "scenario": case.scenario,
                "duration_hours": case.intent.duration_hours,
                "route_count": len(response.routes),
                "hard_violations": case_hard,
                "degradation_level": response.diagnostics.get("degradation_level", 0),
                "failure_reason": "" if response.routes else "no_feasible_route",
                "timings_ms": {
                    "recall": round(recall_ms, 2),
                    "fine_rank": round(fine_ms, 2),
                    "route": round(route_ms, 2),
                    "total": round(total_ms, 2),
                },
                "mean_overlap": round(statistics.mean(case_overlaps), 4) if case_overlaps else 0.0,
            }
        )

    count = len(cases)
    result = {
        "case_count": count,
        "candidate_limit": candidate_limit if candidate_limit is not None else "adaptive",
        "seed": seed,
        "experiment": asdict(experiment),
        "route_success_rate": round(route_success / max(count, 1), 4),
        "three_route_success_rate": round(three_route_success / max(count, 1), 4),
        "hard_constraint_violations": hard_violations,
        "must_include_recall": round(required_hits / required_total, 4) if required_total else None,
        "required_route_missing": required_route_missing,
        "required_role_coverage": round(role_covered / max(role_expected, 1), 4),
        "mean_pairwise_overlap": round(statistics.mean(overlaps), 4) if overlaps else 0.0,
        "p95_latency_ms": round(_percentile(latencies, 0.95), 2),
        "buckets": _bucket_results(case_results),
        "cases": case_results,
    }
    result["gates_passed"] = release_gates(result) == []
    result["gate_failures"] = release_gates(result)
    return result


def release_gates(result: dict[str, Any]) -> list[str]:
    checks = [
        (result["route_success_rate"] >= 0.98, "route_success_rate<0.98"),
        (result["three_route_success_rate"] >= 0.95, "three_route_success_rate<0.95"),
        (result["hard_constraint_violations"] == 0, "hard_constraint_violations>0"),
        (result["must_include_recall"] is None or result["must_include_recall"] >= 0.95, "must_include_recall<0.95"),
        (result["required_route_missing"] == 0, "required_route_missing>0"),
        (result["required_role_coverage"] >= 0.95, "required_role_coverage<0.95"),
        (result["mean_pairwise_overlap"] <= 0.5, "mean_pairwise_overlap>0.5"),
        (result["p95_latency_ms"] <= 3000, "p95_latency_ms>3000"),
    ]
    return [message for passed, message in checks if not passed]


def _bucket_results(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        for key in (f"city:{case['city']}", f"scenario:{case['scenario']}", f"duration:{case['duration_hours']}"):
            buckets.setdefault(key, []).append(case)
    return {
        key: {
            "case_count": len(values),
            "route_success_rate": round(sum(value["route_count"] > 0 for value in values) / len(values), 4),
            "three_route_success_rate": round(sum(value["route_count"] >= 3 for value in values) / len(values), 4),
            "p95_latency_ms": round(_percentile([value["timings_ms"]["total"] for value in values], 0.95), 2),
        }
        for key, values in sorted(buckets.items())
    }


def _pairwise_overlaps(routes: list[Route], exempt_ids: set[str]) -> list[float]:
    values: list[float] = []
    for index, left in enumerate(routes):
        left_ids = {stop.poi_id for stop in left.stops} - exempt_ids
        for right in routes[index + 1 :]:
            right_ids = {stop.poi_id for stop in right.stops} - exempt_ids
            values.append(len(left_ids & right_ids) / max(1, min(len(left_ids), len(right_ids))))
    return values


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * ratio) - 1))]


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    value = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _metadata(seed: int) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return {
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "seed": seed,
    }


def _write_report(output_dir: Path, payload: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "route_strategy_evaluation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# Route Strategy Evaluation", "", f"- Commit: `{payload['metadata']['git_commit']}`", ""]
    for result in payload["results"]:
        lines.extend(
            [
                f"## {result['name']}",
                "",
                f"- Cases: {result['case_count']}",
                f"- Route success: {result['route_success_rate']:.2%}",
                f"- Three routes: {result['three_route_success_rate']:.2%}",
                f"- Role coverage: {result['required_role_coverage']:.2%}",
                f"- P95: {result['p95_latency_ms']:.2f} ms",
                f"- Gates: {'PASS' if result['gates_passed'] else ', '.join(result['gate_failures'])}",
                "",
            ]
        )
    (output_dir / "route_strategy_evaluation.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-limits", default="40,80,120,160,220")
    parser.add_argument("--adaptive", action="store_true")
    parser.add_argument("--experiment", choices=sorted(EXPERIMENTS), default="v2")
    parser.add_argument("--all-ablations", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--assert-gates", action="store_true")
    args = parser.parse_args()
    limits: list[int | None] = [int(value) for value in args.candidate_limits.split(",") if value.strip()]
    if args.adaptive or not limits:
        limits.append(None)
    names = list(EXPERIMENTS) if args.all_ablations else [args.experiment]
    results: list[dict[str, Any]] = []
    for run in range(max(1, args.runs)):
        for name in names:
            for limit in limits:
                result = evaluate(limit, args.max_cases, EXPERIMENTS[name], args.seed + run)
                result["name"] = f"{name}:limit={limit if limit is not None else 'adaptive'}:run={run + 1}"
                results.append(result)
    payload = {"metadata": _metadata(args.seed), "results": results}
    if args.output_dir:
        _write_report(args.output_dir, payload)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.assert_gates and any(not result["gates_passed"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
