from __future__ import annotations

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float
    lng: float


class LiveLegEstimate(BaseModel):
    distance_km: float
    travel_minutes: int
    traffic_multiplier: float = 1.0
    status: str = "normal"
    transport_mode: str = "walk"
    confidence: float = 0.7
    updated_at: str = ""
    source: str = "mock"
    reason: str = ""


class ExternalPOIStatus(BaseModel):
    place_id: str
    status: str = "normal"
    is_open: bool = True
    is_accessible: bool = True
    queue_minutes: int | None = None
    live_crowd_level: float | None = None
    confidence: float = 0.7
    updated_at: str = ""
    valid_until: str = ""
    source: str = "mock"
    reason: str = ""


class ExternalPOICandidate(BaseModel):
    external_place_ids: dict[str, str] = Field(default_factory=dict)
    source_provider: str = "mock"
    name: str
    city: str = "上海"
    district: str = ""
    address: str = ""
    lat: float
    lng: float
    map_category: str = ""
    map_category_code: str = ""
    avg_price: int = 0
    rating: float = 4.2
    review_count: int = 0
    queue_minutes: int = 0
    live_crowd_level: float = 0
    status: str = "normal"
    tags: list[str] = Field(default_factory=list)
