from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.chat import AgentTraceStep
from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import Route
from app.schemas.user import UserProfile


class ToolCallResult(BaseModel):
    tool_name: str
    success: bool
    payload: dict


class ChatTurn(BaseModel):
    role: str
    content: str


class QueryUnderstanding(BaseModel):
    turn_type: str
    inherit_previous: bool = False
    preserve_scenario: bool = False
    target_route_ref: str | None = "current"
    target_stop_ref: str | None = None
    question_type: str | None = None
    confidence: float = 0
    reason: str = ""


class IntentDelta(BaseModel):
    added_hard_constraints: dict[str, object] = Field(default_factory=dict)
    modified_hard_constraints: dict[str, object] = Field(default_factory=dict)
    removed_hard_constraints: list[str] = Field(default_factory=list)
    added_preferences: list[str] = Field(default_factory=list)
    removed_preferences: list[str] = Field(default_factory=list)
    added_avoid_tags: list[str] = Field(default_factory=list)
    removed_avoid_tags: list[str] = Field(default_factory=list)
    added_implicit_needs: list[str] = Field(default_factory=list)
    removed_implicit_needs: list[str] = Field(default_factory=list)
    added_must_include: list[str] = Field(default_factory=list)
    removed_must_include: list[str] = Field(default_factory=list)
    target_route_ref: str | None = "current"
    target_stop_ref: str | None = None


class StateChangeSummary(BaseModel):
    kept: list[str] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)
    changed: dict[str, dict[str, object]] = Field(default_factory=dict)
    removed: list[str] = Field(default_factory=list)


class TripState(BaseModel):
    city: str = "上海"
    people_count: int = 2
    target_district: str | None = None
    target_business_area: str | None = None
    start_time: str = "14:00"
    duration_hours: int = 6
    budget_per_person: int = 300
    scenario: str = "friends_citywalk"
    hard_constraints: dict[str, object] = Field(default_factory=dict)
    soft_preferences: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    optimization_goals: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    implicit_needs: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    active_route_id: str | None = None
    locked_stop_ids: list[str] = Field(default_factory=list)
    feedback_history: list[dict[str, object]] = Field(default_factory=list)

    @classmethod
    def from_intent(cls, intent: Intent) -> "TripState":
        hard_constraints = {
            "city": intent.city,
            "people_count": intent.people_count,
            "target_district": intent.target_district,
            "target_business_area": intent.target_business_area,
            "start_time": intent.start_time,
            "duration_hours": intent.duration_hours,
            "budget_per_person": intent.budget_per_person,
        }
        return cls(
            city=intent.city,
            people_count=intent.people_count,
            target_district=intent.target_district,
            target_business_area=intent.target_business_area,
            start_time=intent.start_time,
            duration_hours=intent.duration_hours,
            budget_per_person=intent.budget_per_person,
            scenario=intent.scenario,
            hard_constraints=hard_constraints,
            soft_preferences=list(intent.preferences),
            interest_tags=list(intent.interest_tags),
            optimization_goals=list(intent.optimization_goals),
            avoid_tags=list(intent.avoid_tags),
            implicit_needs=_default_implicit_needs(intent.duration_hours),
        )

    def to_intent(self) -> Intent:
        return Intent(
            city=self.city,
            people_count=self.people_count,
            target_district=self.target_district,
            target_business_area=self.target_business_area,
            start_time=self.start_time,
            duration_hours=self.duration_hours,
            budget_per_person=self.budget_per_person,
            preferences=list(self.soft_preferences),
            interest_tags=list(self.interest_tags),
            optimization_goals=list(self.optimization_goals),
            avoid_tags=list(self.avoid_tags),
            scenario=self.scenario,
        )


class SessionState(BaseModel):
    session_id: str
    recent_messages: list[ChatTurn] = Field(default_factory=list)
    last_intent: Intent | None = None
    trip_state: TripState | None = None
    current_routes: list[Route] = Field(default_factory=list)
    user_profile: UserProfile | None = None
    clarification_count: int = 0


class AgentState(BaseModel):
    session_id: str
    message: str
    intent: Intent | None = None
    user_profile: UserProfile | None = None
    candidate_pois: list[POI] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    agent_trace: list[AgentTraceStep] = Field(default_factory=list)


def _default_implicit_needs(duration_hours: int) -> list[str]:
    if duration_hours >= 6:
        return ["meal_stop", "rest_stop"]
    if duration_hours >= 4:
        return ["rest_stop"]
    return []
