from fastapi import APIRouter

from app.schemas.route import RoutePlanRequest, RoutePlanResponse, ReplanRequest
from app.services.route_service import RouteService
from app.services.replan_service import ReplanService

router = APIRouter(tags=["routes"])
route_service = RouteService()
replan_service = ReplanService()


@router.post("/routes/plan", response_model=RoutePlanResponse)
def plan_routes(request: RoutePlanRequest) -> RoutePlanResponse:
    return route_service.generate_routes(request)


@router.post("/routes/replan", response_model=RoutePlanResponse)
def replan_route(request: ReplanRequest) -> RoutePlanResponse:
    return replan_service.replan(request)

