from app.schemas.intent import Intent
from app.schemas.route import RoutePlanRequest
from app.services.poi_service import POIService
from app.services.profile_service import ProfileService
from app.services.route_service import RouteService


def test_generate_routes() -> None:
    intent = Intent()
    profile_service = ProfileService()
    profile = profile_service.get_profile("user_demo")
    pois = POIService().search(intent)
    response = RouteService().generate_routes(
        RoutePlanRequest(intent=intent, user_profile=profile, candidate_pois=pois)
    )
    assert len(response.routes) == 3

