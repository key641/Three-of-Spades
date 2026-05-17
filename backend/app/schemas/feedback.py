from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    route_id: str
    route_score: int
    restaurant_score: int
    queue_score: int
    budget_score: int
    comment: str = ""


class FeedbackResponse(BaseModel):
    user_id: str
    updated_tags: list[str]
    message: str

