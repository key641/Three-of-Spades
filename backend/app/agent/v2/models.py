from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ConstraintSource(str, Enum):
    USER_EXPLICIT = "user_explicit"
    HISTORY_EXPLICIT = "history_explicit"
    GPS = "gps"
    PROFILE = "profile"
    INFERRED = "inferred"
    DEFAULT = "default"


SOURCE_PRIORITY = {
    ConstraintSource.DEFAULT: 10,
    ConstraintSource.INFERRED: 20,
    ConstraintSource.PROFILE: 30,
    ConstraintSource.GPS: 40,
    ConstraintSource.HISTORY_EXPLICIT: 50,
    ConstraintSource.USER_EXPLICIT: 60,
}


class Relaxability(str, Enum):
    HARD = "hard"
    ASK_BEFORE_RELAX = "ask_before_relax"
    SOFT = "soft"


class ConstraintValue(BaseModel):
    value: Any
    source: ConstraintSource
    confidence: float = Field(default=1.0, ge=0, le=1)
    turn_id: str
    relaxability: Relaxability = Relaxability.SOFT
    evidence: str | None = None


class LocationRef(BaseModel):
    name: str | None = None
    lat: float | None = None
    lng: float | None = None
    city: str | None = None
    precision: Literal["exact", "gps", "area", "city_default"] = "area"


class StatePatch(BaseModel):
    op: Literal["add", "replace", "remove"]
    path: str
    value: Any = None
    source: ConstraintSource = ConstraintSource.USER_EXPLICIT
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: str | None = None
    relaxability: Relaxability | None = None


class AmbiguitySignal(BaseModel):
    field: str | None = None
    kind: Literal["missing", "conflict", "vague", "unsupported"] = "vague"
    description: str
    candidate_values: list[Any] = Field(default_factory=list)


class TurnUnderstanding(BaseModel):
    turn_type: Literal[
        "new_plan", "add", "modify", "remove", "route_question", "replan", "select", "chat"
    ] = "new_plan"
    state_patch: list[StatePatch] = Field(default_factory=list)
    route_id: str | None = None
    stop_id: str | None = None
    scope: str = "current_trip"
    ambiguities: list[AmbiguitySignal] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    mode: Literal["llm", "fallback", "hybrid"] = "fallback"

    @field_validator("ambiguities", mode="before")
    @classmethod
    def normalize_legacy_ambiguities(cls, value):
        if not value:
            return []
        return [
            {"kind": "vague", "description": item}
            if isinstance(item, str)
            else item
            for item in value
        ]


class StateEvent(BaseModel):
    event_id: str
    session_id: str
    turn_id: str
    base_version: int
    new_version: int
    event_type: str
    patches: list[StatePatch] = Field(default_factory=list)
    created_at: str


class StateChangeSummaryV2(BaseModel):
    kept: list[str] = Field(default_factory=list)
    changed: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    ignored: list[str] = Field(default_factory=list)


class PlanningOutcomeV2(BaseModel):
    status: Literal["complete", "partial", "clarification", "infeasible", "degraded", "failed"]
    route_ids: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ToolStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    INFEASIBLE = "infeasible"
    RETRYABLE_ERROR = "retryable_error"
    FATAL_ERROR = "fatal_error"
    INVALID_INPUT = "invalid_input"


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 5000
    side_effect: Literal["none", "idempotent", "mutating"] = "none"
    max_attempts: int = 1


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    status: ToolStatus
    data: Any = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    suggested_next_actions: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    error_code: str | None = None
    safe_message: str | None = None


class TripStateV2(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    session_id: str
    state_version: int = 0
    city: ConstraintValue | None = None
    people_count: ConstraintValue | None = None
    start_location: ConstraintValue | None = None
    start_time: ConstraintValue | None = None
    duration_minutes: ConstraintValue | None = None
    budget_per_person: ConstraintValue | None = None
    target_district: ConstraintValue | None = None
    target_business_area: ConstraintValue | None = None
    scenario: ConstraintValue | None = None
    preferences: list[ConstraintValue] = Field(default_factory=list)
    avoidances: list[ConstraintValue] = Field(default_factory=list)
    must_include: list[ConstraintValue] = Field(default_factory=list)
    implicit_needs: list[ConstraintValue] = Field(default_factory=list)
    active_route_id: str | None = None
    current_route_ids: list[str] = Field(default_factory=list)
    route_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    locked_stop_ids: list[str] = Field(default_factory=list)
    unresolved_fields: dict[str, str] = Field(default_factory=dict)
    last_outcome: PlanningOutcomeV2 | None = None

    def scalar_value(self, field: str, default: Any = None) -> Any:
        wrapped = getattr(self, field, None)
        return wrapped.value if isinstance(wrapped, ConstraintValue) else default
