from app.schemas.route import ReplanRequest, RoutePlanResponse
from app.services.replan_service import ReplanService


service = ReplanService()


def replan_route(request: ReplanRequest) -> RoutePlanResponse:
    return service.replan(request)

