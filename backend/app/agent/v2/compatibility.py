from __future__ import annotations

from app.agent.schemas import SessionState
from app.agent.v2.models import (
    ConstraintSource,
    ConstraintValue,
    LocationRef,
    Relaxability,
    TripStateV2,
)
from app.schemas.intent import Intent
from app.schemas.route import Route
from app.agent.v2.temporal import normalize_clock_time


def legacy_to_v2(session_id: str, legacy: SessionState | None) -> TripStateV2:
    state = TripStateV2(session_id=session_id)
    if legacy is None or legacy.last_intent is None:
        return state
    intent = legacy.last_intent
    turn_id = "legacy_migration"
    explicit = Relaxability.ASK_BEFORE_RELAX

    def value(raw, source=ConstraintSource.HISTORY_EXPLICIT, relaxability=explicit):
        return ConstraintValue(
            value=raw, source=source, confidence=0.9, turn_id=turn_id,
            relaxability=relaxability, evidence="legacy session migration",
        )

    state.city = value(intent.city)
    state.people_count = value(intent.people_count)
    state.start_time = value(intent.start_time)
    state.duration_minutes = value(intent.duration_hours * 60)
    state.budget_per_person = value(intent.budget_per_person)
    state.scenario = value(intent.scenario, ConstraintSource.INFERRED, Relaxability.SOFT)
    if intent.start_location_name or (intent.start_lat is not None and intent.start_lng is not None):
        source = ConstraintSource.GPS if intent.start_location_name == "当前位置" else ConstraintSource.HISTORY_EXPLICIT
        state.start_location = value(
            LocationRef(
                name=intent.start_location_name,
                lat=intent.start_lat,
                lng=intent.start_lng,
                city=intent.city,
                precision="gps" if source == ConstraintSource.GPS else "exact",
            ),
            source,
            Relaxability.SOFT if source == ConstraintSource.GPS else explicit,
        )
    state.preferences = [value(item) for item in intent.preferences]
    state.avoidances = [value(item) for item in intent.avoid_tags]
    state.must_include = [value(item) for item in [*intent.must_include_poi_ids, *intent.must_include_roles]]
    state.current_route_ids = [route.route_id for route in legacy.current_routes]
    state.route_snapshots = [route.model_dump() for route in legacy.current_routes]
    state.active_route_id = state.current_route_ids[0] if state.current_route_ids else None
    return state


def state_to_intent(state: TripStateV2) -> Intent:
    location = state.scalar_value("start_location")
    if isinstance(location, dict):
        location = LocationRef.model_validate(location)
    must_values = [str(item.value) for item in state.must_include]
    implicit_roles = [str(item.value) for item in state.implicit_needs]
    return Intent(
        city=str(state.scalar_value("city", "上海")),
        people_count=int(state.scalar_value("people_count", 2)),
        start_location_name=location.name if isinstance(location, LocationRef) else None,
        start_lat=location.lat if isinstance(location, LocationRef) else None,
        start_lng=location.lng if isinstance(location, LocationRef) else None,
        start_time=normalize_clock_time(state.scalar_value("start_time", "14:00")) or "14:00",
        duration_hours=max(1, round(int(state.scalar_value("duration_minutes", 360)) / 60)),
        budget_per_person=int(state.scalar_value("budget_per_person", 300)),
        target_district=state.scalar_value("target_district"),
        target_business_area=state.scalar_value("target_business_area"),
        preferences=[str(item.value) for item in state.preferences],
        avoid_tags=[str(item.value) for item in state.avoidances],
        must_include_poi_ids=[item for item in must_values if item.startswith("poi_")],
        must_include_roles=list(dict.fromkeys([
            *[item for item in must_values if not item.startswith("poi_")],
            *implicit_roles,
        ])),
        scenario=str(state.scalar_value("scenario", "friends_citywalk")),
        city_from_message=bool(state.city and state.city.source == ConstraintSource.USER_EXPLICIT),
    )


def restored_routes(state: TripStateV2) -> list[Route]:
    routes: list[Route] = []
    for payload in state.route_snapshots:
        try:
            routes.append(Route.model_validate(payload))
        except Exception:
            continue
    return routes
