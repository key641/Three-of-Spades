from pydantic import BaseModel, Field


class StrategyWeights(BaseModel):
    quality: float = 0.3
    queue: float = 0.25
    distance: float = 0.2
    budget: float = 0.15
    preference: float = 0.1


class UserProfile(BaseModel):
    user_id: str
    tags: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    preference_weights: dict[str, float] = Field(default_factory=dict)
