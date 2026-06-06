from pydantic import BaseModel, Field

from app.agent.tag_taxonomy import (
    legacy_preferences_from_layers,
    normalize_avoid_tags,
    normalize_interest_tags,
    normalize_optimization_goals,
    split_preference_terms,
)


class Intent(BaseModel):
    city: str = "上海"
    people_count: int = 2
    start_location_name: str | None = None
    start_lat: float | None = None
    start_lng: float | None = None
    start_time: str = "14:00"
    duration_hours: int = 6
    budget_per_person: int = 300
    preferences: list[str] = Field(default_factory=list)
    interest_tags: list[str] = Field(default_factory=list)
    optimization_goals: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=list)
    scenario: str = "friends_citywalk"
    need_clarification: bool = False
    city_from_message: bool = False

    def model_post_init(self, __context: object) -> None:
        layers = split_preference_terms(self.preferences)
        self.interest_tags = normalize_interest_tags([*self.interest_tags, *layers.interest_tags])
        self.optimization_goals = normalize_optimization_goals([*self.optimization_goals, *layers.optimization_goals])
        self.avoid_tags = normalize_avoid_tags([*self.avoid_tags, *layers.avoid_tags])
        self.preferences = legacy_preferences_from_layers(
            self.interest_tags,
            self.optimization_goals,
            layers.unknown_preferences,
        )
