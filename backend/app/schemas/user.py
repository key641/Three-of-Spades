from pydantic import BaseModel, Field


class StrategyWeights(BaseModel):
    quality: float = 0.3
    queue: float = 0.25
    distance: float = 0.2
    budget: float = 0.15
    preference: float = 0.1


class StrategyTag(BaseModel):
    tag: str
    intensity: float = 0.5
    polarity: str = "prefer"
    evidence: str = ""


class UserProfile(BaseModel):
    user_id: str
    tags: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    preference_weights: dict[str, float] = Field(default_factory=dict)
    budget_sensitivity: float = 0.5
    walking_tolerance: float = 0.5
    crowd_tolerance: float = 0.5
    schedule_tightness: float = 0.5
    novelty_preference: float = 0.5
    comfort_preference: float = 0.5
    category_preferences: dict[str, float] = Field(default_factory=dict)
    preferred_route_roles: list[str] = Field(default_factory=list)
    preferred_experience_tags: list[str] = Field(default_factory=list)
    preferred_time_slots: list[str] = Field(default_factory=list)
    preferred_transport_modes: list[str] = Field(default_factory=list)
    liked_poi_ids: list[str] = Field(default_factory=list)
    disliked_poi_ids: list[str] = Field(default_factory=list)
    skipped_categories: list[str] = Field(default_factory=list)
    common_adjust_actions: list[str] = Field(default_factory=list)
