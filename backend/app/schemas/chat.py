from pydantic import BaseModel
from pydantic import Field
from typing import Any

from app.schemas.intent import Intent
from app.schemas.route import Route
from app.schemas.user import UserProfile


class ChatRequest(BaseModel):
    session_id: str = "session_demo"
    user_id: str = "user_demo"
    message: str
    event_type: str = "user_message"
    city: str | None = None
    scenarios: list[str] = Field(default_factory=list)
    scenario: str | None = None
    preferences: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    budget_level: str | None = None
    preference_weights: dict[str, float] | None = None
    start_location_name: str | None = None
    start_lat: float | None = None
    start_lng: float | None = None
    current_lat: float | None = None
    current_lng: float | None = None
    selected_route_id: str | None = None
    target_poi_id: str | None = None
    event_payload: dict[str, Any] = Field(default_factory=dict)
    budget_sensitivity: float | None = None
    walking_tolerance: float | None = None
    crowd_tolerance: float | None = None
    schedule_tightness: float | None = None
    novelty_preference: float | None = None
    comfort_preference: float | None = None
    category_preferences: dict[str, float] | None = None
    preferred_route_roles: list[str] = Field(default_factory=list)
    preferred_experience_tags: list[str] = Field(default_factory=list)
    preferred_time_slots: list[str] = Field(default_factory=list)
    preferred_transport_modes: list[str] = Field(default_factory=list)
    liked_poi_ids: list[str] = Field(default_factory=list)
    disliked_poi_ids: list[str] = Field(default_factory=list)
    skipped_categories: list[str] = Field(default_factory=list)
    common_adjust_actions: list[str] = Field(default_factory=list)


class AgentTraceStep(BaseModel):
    step: str
    label: str
    status: str
    details: dict[str, object] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    message: str
    need_clarification: bool
    clarifying_question: str | None = None
    intent: Intent | None = None
    user_profile: UserProfile | None = None
    routes: list[Route]
    agent_trace: list[AgentTraceStep]
