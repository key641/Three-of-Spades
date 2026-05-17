from fastapi import APIRouter

from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.profile_service import ProfileService

router = APIRouter(tags=["feedback"])
profile_service = ProfileService()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    return profile_service.update_from_feedback(request)

