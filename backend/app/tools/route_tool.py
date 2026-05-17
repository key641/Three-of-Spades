from app.schemas.route import RoutePlanRequest, RoutePlanResponse
from app.services.route_service import RouteService


service = RouteService()


def generate_routes(request: RoutePlanRequest) -> RoutePlanResponse:
    return service.generate_routes(request)

