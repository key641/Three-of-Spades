from pydantic import BaseModel, Field


class Intent(BaseModel):
    city: str = "上海"
    people_count: int = 2
    start_time: str = "14:00"
    duration_hours: int = 6
    budget_per_person: int = 300
    preferences: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    scenario: str = "friends_citywalk"
    need_clarification: bool = False

