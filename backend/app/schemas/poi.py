from pydantic import BaseModel, Field


class POI(BaseModel):
    id: str
    name: str
    city: str
    district: str = ""
    business_area: str = ""
    address: str = ""
    category: str
    external_place_ids: dict[str, str] = Field(default_factory=dict)
    source_provider: str = "local"
    source_updated_at: str = ""
    map_category: str = ""
    map_category_code: str = ""
    geohash: str = ""
    canonical_poi_id: str = ""
    primary_category: str = ""
    secondary_categories: list[str] = Field(default_factory=list)
    route_roles: list[str] = Field(default_factory=list)
    experience_tags: list[str] = Field(default_factory=list)
    lat: float
    lng: float
    avg_price: int
    price_min: int = 0
    price_max: int = 0
    rating: float
    review_count: int = 0
    popularity: float = 0
    crowd_level: float = 0
    queue_minutes: int
    live_crowd_level: float = 0
    visit_duration_minutes: int
    open_time: str = "00:00"
    close_time: str = "23:59"
    last_entry_time: str = "23:59"
    open_hours: str
    need_booking: bool = False
    suitable_time_slots: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    negative_tags: list[str] = Field(default_factory=list)
    family_friendly: float
    couple_friendly: float = 0
    friends_friendly: float = 0
    solo_friendly: float = 0
    elderly_friendly: float = 0
    rainy_day_score: float = 0
    budget_friendly: float = 0
    photo_friendly: float = 0
    food_nearby: float = 0
    night_activity: float = 0
    indoor: bool
    walking_intensity: str = "medium"
    recommended_transport: list[str] = Field(default_factory=list)
    nearby_poi_ids: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    avoid_reasons: list[str] = Field(default_factory=list)
    meal_type: str = "non_meal"
    transit_hub_nearby: bool = False
    parking_available: bool = False
    cover_image_url: str = ""
    highlight_text: str = ""
    highlight_text_tags: list[str] = Field(default_factory=list)
    ugc_tip: str = ""
