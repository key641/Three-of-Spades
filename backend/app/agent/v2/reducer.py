from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import uuid

from app.agent.v2.models import (
    ConstraintSource,
    ConstraintValue,
    LocationRef,
    Relaxability,
    SOURCE_PRIORITY,
    StateChangeSummaryV2,
    StateEvent,
    StatePatch,
    TripStateV2,
    TurnUnderstanding,
)


SCALAR_FIELDS = {
    "city",
    "people_count",
    "start_location",
    "start_time",
    "duration_minutes",
    "budget_per_person",
    "target_district",
    "target_business_area",
    "scenario",
}
LIST_FIELDS = {"preferences", "avoidances", "must_include", "implicit_needs"}


def reduce_state(
    old_state: TripStateV2,
    understanding: TurnUnderstanding,
    turn_id: str,
) -> tuple[TripStateV2, StateEvent, StateChangeSummaryV2]:
    state = deepcopy(old_state)
    summary = StateChangeSummaryV2()
    applied: list[StatePatch] = []

    if understanding.turn_type == "new_plan" and old_state.state_version > 0:
        state.active_route_id = None
        state.current_route_ids = []
        state.locked_stop_ids = []
        state.last_outcome = None

    for patch in understanding.state_patch:
        field = patch.path.strip("/")
        if field in SCALAR_FIELDS:
            if _apply_scalar(state, field, patch, turn_id):
                applied.append(patch)
                (summary.removed if patch.op == "remove" else summary.changed).append(field)
            else:
                summary.ignored.append(field)
        elif field in LIST_FIELDS:
            if _apply_list(state, field, patch, turn_id):
                applied.append(patch)
                (summary.removed if patch.op == "remove" else summary.changed).append(field)
            else:
                summary.ignored.append(field)

    base_version = old_state.state_version
    state.state_version = base_version + 1
    event = StateEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        session_id=state.session_id,
        turn_id=turn_id,
        base_version=base_version,
        new_version=state.state_version,
        event_type=understanding.turn_type,
        patches=applied,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return state, event, summary


def _apply_scalar(state: TripStateV2, field: str, patch: StatePatch, turn_id: str) -> bool:
    current = getattr(state, field)
    if patch.op == "remove":
        setattr(state, field, None)
        return current is not None
    incoming = ConstraintValue(
        value=_coerce_value(field, patch.value),
        source=patch.source,
        confidence=patch.confidence,
        turn_id=turn_id,
        relaxability=patch.relaxability or _default_relaxability(patch.source),
        evidence=patch.evidence,
    )
    if current is not None and SOURCE_PRIORITY[incoming.source] < SOURCE_PRIORITY[current.source]:
        return False
    setattr(state, field, incoming)
    return True


def _apply_list(state: TripStateV2, field: str, patch: StatePatch, turn_id: str) -> bool:
    current: list[ConstraintValue] = list(getattr(state, field))
    values = patch.value if isinstance(patch.value, list) else [patch.value]
    normalized = [str(value).strip() for value in values if str(value).strip()]
    if patch.op == "remove":
        updated = [item for item in current if str(item.value) not in normalized]
        setattr(state, field, updated)
        return len(updated) != len(current)
    by_value = {str(item.value): item for item in current}
    changed = False
    for value in normalized:
        existing = by_value.get(value)
        if existing and SOURCE_PRIORITY[existing.source] > SOURCE_PRIORITY[patch.source]:
            continue
        by_value[value] = ConstraintValue(
            value=value,
            source=patch.source,
            confidence=patch.confidence,
            turn_id=turn_id,
            relaxability=patch.relaxability or _default_relaxability(patch.source),
            evidence=patch.evidence,
        )
        changed = True
    setattr(state, field, list(by_value.values()))
    return changed


def _coerce_value(field: str, value):
    if field == "start_location":
        return value if isinstance(value, LocationRef) else LocationRef.model_validate(value)
    if field in {"people_count", "duration_minutes", "budget_per_person"}:
        return int(value)
    return value


def _default_relaxability(source: ConstraintSource) -> Relaxability:
    if source in {ConstraintSource.USER_EXPLICIT, ConstraintSource.HISTORY_EXPLICIT}:
        return Relaxability.ASK_BEFORE_RELAX
    return Relaxability.SOFT
