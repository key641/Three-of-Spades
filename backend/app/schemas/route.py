from pydantic import BaseModel, Field

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.user import StrategyWeights, UserProfile


class RouteStop(BaseModel):
    poi_id: str
    name: str
    category: str
    start_time: str
    end_time: str
    estimated_cost: int
    queue_minutes: int
    tags: list[str]


class RouteScoreBreakdown(BaseModel):
    quality: int
    queue: int
    budget: int
    distance: int
    preference: int


class Route(BaseModel):
    route_id: str
    title: str
    objective: str
    summary: str
    total_duration_minutes: int
    total_cost_per_person: int
    total_queue_minutes: int
    score: int
    score_breakdown: RouteScoreBreakdown
    stops: list[RouteStop]
    reasons: list[str]
    replan_reason: str | None = None


class RoutePlanRequest(BaseModel):
    intent: Intent
    user_profile: UserProfile
    strategy_weights: StrategyWeights = Field(default_factory=StrategyWeights)
    candidate_pois: list[POI] = Field(default_factory=list)


class RoutePlanResponse(BaseModel):
    routes: list[Route]


class ReplanRequest(BaseModel):
    session_id: str
    event_type: str
    event_label: str
    current_routes: list[Route]
    completed_poi_ids: list[str] = Field(default_factory=list)

