from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    route_id: str
    route_score: int
    restaurant_score: int
    queue_score: int
    budget_score: int
    comment: str = ""
    event_type: str = "route_feedback"
    request_id: str = ""
    algorithm_version: str = "planning_v2"
    selected_poi_ids: list[str] = Field(default_factory=list)
    completed_poi_ids: list[str] = Field(default_factory=list)
    replaced_poi_ids: list[str] = Field(default_factory=list)
    abandoned: bool = False


class FeedbackResponse(BaseModel):
    user_id: str
    updated_tags: list[str]
    message: str
