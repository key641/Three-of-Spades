from __future__ import annotations

import json

from app.schemas.feedback import FeedbackRequest
from app.schemas.intent import Intent
from app.schemas.route import Route, RoutePlanRequest
from app.schemas.user import UserProfile
from app.services.route_signal_service import RouteSignalService


def test_route_signal_service_records_route_level_feedback(tmp_path) -> None:
    output = tmp_path / "route_signals.jsonl"
    service = RouteSignalService(output)
    service.record(
        FeedbackRequest(
            user_id="u",
            session_id="s",
            route_id="r",
            route_score=5,
            restaurant_score=4,
            queue_score=3,
            budget_score=4,
            selected_poi_ids=["p1"],
            completed_poi_ids=["p1"],
            replaced_poi_ids=["p2"],
        )
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["selected_poi_ids"] == ["p1"]
    assert payload["completed_poi_ids"] == ["p1"]
    assert payload["replaced_poi_ids"] == ["p2"]
    assert payload["recorded_at"]


def test_sqlite_signal_store_records_impressions_feedback_and_exports(tmp_path) -> None:
    db_path = tmp_path / "route_signals.db"
    service = RouteSignalService(db_path=db_path)
    route = Route.model_validate(
        {
            "route_id": "r1",
            "title": "路线",
            "objective": "balanced",
            "summary": "summary",
            "total_duration_minutes": 60,
            "total_cost_per_person": 50,
            "total_queue_minutes": 0,
            "score": 80,
            "score_breakdown": {"quality": 80, "queue": 80, "budget": 80, "distance": 80, "preference": 80},
            "stops": [{"poi_id": "p1", "name": "P1", "category": "gallery", "start_time": "10:00", "end_time": "11:00", "estimated_cost": 50, "queue_minutes": 0, "tags": []}],
            "reasons": [],
        }
    )
    request = RoutePlanRequest(intent=Intent(), user_profile=UserProfile(user_id="u"))
    service.record_impression("req1", "s", request, [route])
    service.record(
        FeedbackRequest(
            user_id="u", session_id="s", route_id="r1", route_score=5,
            restaurant_score=5, queue_score=5, budget_score=5, event_type="route_selected", request_id="req1"
        )
    )
    output = tmp_path / "export.jsonl"

    assert service.counts()["impressions"] == 1
    assert service.counts()["selections"] == 1
    assert service.export_jsonl(output) == 2
    assert len(output.read_text(encoding="utf-8").splitlines()) == 2
