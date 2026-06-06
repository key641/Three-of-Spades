from fastapi import APIRouter

from app.schemas.route import (
    ReplanRequest,
    RouteEvaluationRequest,
    RouteEvaluationResponse,
    RoutePlanRequest,
    RoutePlanResponse,
)
from app.services.route_evaluation_service import RouteEvaluationService
from app.services.route_service import RouteService
from app.services.replan_service import ReplanService

router = APIRouter(tags=["routes"])
route_service = RouteService()
replan_service = ReplanService()
route_evaluation_service = RouteEvaluationService()


@router.post("/routes/plan", response_model=RoutePlanResponse)
def plan_routes(request: RoutePlanRequest) -> RoutePlanResponse:
    return route_service.generate_routes(request)


@router.post("/routes/evaluate", response_model=RouteEvaluationResponse)
async def evaluate_routes(request: RouteEvaluationRequest) -> RouteEvaluationResponse:
    return await route_evaluation_service.evaluate(request)


@router.post("/routes/replan", response_model=RoutePlanResponse)
def replan_route(request: ReplanRequest) -> RoutePlanResponse:
    return replan_service.replan(request)
