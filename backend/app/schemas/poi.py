from pydantic import BaseModel


class POI(BaseModel):
    id: str
    name: str
    city: str
    category: str
    lat: float
    lng: float
    avg_price: int
    rating: float
    queue_minutes: int
    visit_duration_minutes: int
    open_hours: str
    tags: list[str]
    negative_tags: list[str]
    family_friendly: float
    indoor: bool

