from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.services.profile_service import ProfileService


service = ProfileService()


def update_profile_from_feedback(request: FeedbackRequest) -> FeedbackResponse:
    return service.update_from_feedback(request)

