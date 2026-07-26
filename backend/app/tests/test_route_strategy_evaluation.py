from __future__ import annotations

from app.services.poi_service import POIService
from scripts.evaluate_route_strategy import build_cases, release_gates


def test_evaluation_suite_contains_120_balanced_city_cases() -> None:
    cases = build_cases(POIService())

    assert len(cases) == 120
    assert sum(case.intent.city == "上海" for case in cases) == 60
    assert sum(case.intent.city == "北京" for case in cases) == 60


def test_release_gates_accept_metrics_at_thresholds() -> None:
    assert release_gates(
        {
            "route_success_rate": 0.98,
            "three_route_success_rate": 0.95,
            "hard_constraint_violations": 0,
            "must_include_recall": 0.95,
            "required_route_missing": 0,
            "required_role_coverage": 0.95,
            "mean_pairwise_overlap": 0.5,
            "p95_latency_ms": 3000,
        }
    ) == []
