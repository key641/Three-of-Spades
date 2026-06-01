from pydantic import BaseModel, Field

from typing import Any

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyTag, StrategyWeights, UserProfile


class RouteStop(BaseModel):
    poi_id: str
    name: str
    category: str
    primary_category: str = ""
    secondary_categories: list[str] = Field(default_factory=list)
    route_roles: list[str] = Field(default_factory=list)
    experience_tags: list[str] = Field(default_factory=list)
    district: str = ""
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    start_time: str
    end_time: str
    estimated_cost: int
    queue_minutes: int
    tags: list[str]
    meal_type: str = "non_meal"
    open_hours: str = ""
    last_entry_time: str = ""
    walking_intensity: str = "medium"
    cover_image_url: str = ""
    highlight_text: str = ""
    ugc_tip: str = ""
    indoor: bool = False
    recommended_transport: list[str] = Field(default_factory=list)
    travel_minutes_from_previous: int | None = None
    distance_km_from_previous: float | None = None
    transport_mode_from_previous: str | None = None
    polyline_from_previous: str = ""
    amap_distance_meters_from_previous: int | None = None
    amap_duration_minutes_from_previous: int | None = None
    route_leg_source_from_previous: str | None = None
    route_steps_from_previous: list[str] = Field(default_factory=list)
    reason: str | None = None


class RouteScoreBreakdown(BaseModel):
    quality: int
    queue: int
    budget: int
    distance: int
    preference: int


class RouteChange(BaseModel):
    change_type: str
    from_poi_id: str | None = None
    from_name: str | None = None
    to_poi_id: str | None = None
    to_name: str | None = None
    reason: str


class Route(BaseModel):
    route_id: str
    title: str
    objective: str
    summary: str
    total_duration_minutes: int
    total_cost_per_person: int
    total_queue_minutes: int
    total_travel_minutes: int = 0
    total_distance_km: float = 0
    score: int
    score_breakdown: RouteScoreBreakdown
    stops: list[RouteStop]
    reasons: list[str]
    replan_reason: str | None = None
    changed_stops: list[RouteChange] = Field(default_factory=list)
    live_warnings: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


class RoutePlanRequest(BaseModel):
    intent: Intent
    user_profile: UserProfile
    strategy_weights: StrategyWeights = Field(default_factory=StrategyWeights)
    strategy_tags: list[StrategyTag] = Field(default_factory=list)
    candidate_pois: list[POI] = Field(default_factory=list)


class RoutePlanResponse(BaseModel):
    routes: list[Route]


class RouteEvaluationRequest(BaseModel):
    intent: Intent
    routes: list[Route]
    user_profile: UserProfile | None = None


class RouteEvaluation(BaseModel):
    route_id: str
    score: int
    summary: str
    highlights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendation: str = ""
    source: str = "fallback"


class RouteEvaluationResponse(BaseModel):
    evaluations: list[RouteEvaluation]


class ReplanRequest(BaseModel):
    session_id: str
    event_type: str
    event_label: str
    current_routes: list[Route]
    completed_poi_ids: list[str] = Field(default_factory=list)
    selected_route_id: str | None = None
    current_poi_id: str | None = None
    current_lat: float | None = None
    current_lng: float | None = None
    current_time: str | None = None
    locked_poi_ids: list[str] = Field(default_factory=list)
    event_payload: dict[str, Any] = Field(default_factory=dict)
    intent: Intent | None = None
    user_profile: UserProfile | None = None
