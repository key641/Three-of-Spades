from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.services.poi_service import POIService


service = POIService()


def search_pois(intent: Intent) -> list[POI]:
    return service.search(intent)

