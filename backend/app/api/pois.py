from fastapi import APIRouter

from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.services.poi_service import POIService

router = APIRouter(tags=["pois"])
poi_service = POIService()


@router.post("/pois/search", response_model=list[POI])
def search_pois(intent: Intent) -> list[POI]:
    return poi_service.search(intent=intent)

