from fastapi import APIRouter

from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.profile_service import ProfileService
from app.services.route_signal_service import RouteSignalService

router = APIRouter(tags=["feedback"])
profile_service = ProfileService()
route_signal_service = RouteSignalService()


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    route_signal_service.record(request)
    return profile_service.update_from_feedback(request)
