from __future__ import annotations

from app.schemas.intent import Intent
from app.schemas.route import Route, RoutePlanRequest, RouteScoreBreakdown, RouteStop
from app.schemas.user import UserProfile
from app.services.constraint_evaluator import ConstraintEvaluator


def _route() -> Route:
    return Route(
        route_id="r",
        title="r",
        objective="balanced",
        summary="",
        total_duration_minutes=200,
        total_cost_per_person=120,
        total_queue_minutes=20,
        total_travel_minutes=30,
        score=80,
        score_breakdown=RouteScoreBreakdown(quality=80, queue=80, budget=80, distance=80, preference=80),
        stops=[
            RouteStop(
                poi_id="required",
                name="required",
                category="landmark",
                start_time="10:00",
                end_time="11:00",
                estimated_cost=120,
                queue_minutes=20,
                tags=[],
            )
        ],
        reasons=[],
    )


def test_missing_required_poi_is_hard_violation() -> None:
    route = _route()
    request = RoutePlanRequest(
        intent=Intent(must_include_poi_ids=["another"]),
        user_profile=UserProfile(user_id="u"),
    )
    result = ConstraintEvaluator().evaluate_route(route, request, {})

    assert not result.feasible
    assert "missing_required:another" in result.hard_violations


def test_reliability_uses_p80_and_buffer() -> None:
    route = _route()
    request = RoutePlanRequest(intent=Intent(duration_hours=5), user_profile=UserProfile(user_id="u"))
    evaluator = ConstraintEvaluator()
    result = evaluator.evaluate_route(route, request, {})
    p80, buffer_minutes, reliability, risk_level = evaluator.reliability(route, request, result)

    assert p80 > route.total_duration_minutes
    assert buffer_minutes == request.intent.duration_hours * 60 - p80
    assert 0 <= reliability <= 1
    assert risk_level in {"low", "medium", "high"}
