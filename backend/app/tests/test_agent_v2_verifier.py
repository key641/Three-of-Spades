from app.agent.v2.response_composer import ResponseComposer
from app.agent.v2.verifier import OutcomeVerifier
from app.schemas.intent import Intent
from app.schemas.route import Route, RouteScoreBreakdown, RouteStop
from app.schemas.user import UserProfile


def build_route(route_id="r1", duplicate=False):
    stop = RouteStop(
        poi_id="p1", name="A", category="park", primary_category="nature",
        district="", business_area="", address="", lat=31.2, lng=121.4,
        start_time="10:00", end_time="11:00", estimated_cost=0, queue_minutes=0,
        tags=[], meal_type="non_meal", open_hours="全天", last_entry_time="23:59",
        walking_intensity="low", cover_image_url="", highlight_text="", ugc_tip="",
        indoor=False, recommended_transport=[],
    )
    stops = [stop, stop.model_copy()] if duplicate else [stop]
    return Route(
        route_id=route_id, title="路线", objective="balanced", summary="",
        total_duration_minutes=60, total_cost_per_person=0, total_queue_minutes=0,
        score=80, score_breakdown=RouteScoreBreakdown(
            quality=80, queue=80, budget=80, distance=80, preference=80,
        ), stops=stops, reasons=[],
    )


def test_verifier_rejects_duplicate_and_unknown_stops() -> None:
    report = OutcomeVerifier().verify(
        [build_route(duplicate=True)], Intent(), UserProfile(user_id="u"), []
    )
    assert report.valid_routes == []
    assert {issue.code for issue in report.issues} >= {"duplicate_stop", "unknown_poi"}


def test_response_composer_returns_partial_routes_without_claiming_three() -> None:
    message = ResponseComposer().compose_routes(Intent(), [build_route()])
    assert "1 条可执行路线" in message
    assert "3 条" not in message
