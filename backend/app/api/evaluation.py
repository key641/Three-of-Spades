from fastapi import APIRouter

from app.schemas.evaluation import EvaluationRunRequest, EvaluationRunResponse
from app.services.evaluation_service import EvaluationService


router = APIRouter(tags=["evaluation"])
evaluation_service = EvaluationService()


@router.post("/evaluation/run", response_model=EvaluationRunResponse)
async def run_evaluation(request: EvaluationRunRequest) -> EvaluationRunResponse:
    return await evaluation_service.run(request)
