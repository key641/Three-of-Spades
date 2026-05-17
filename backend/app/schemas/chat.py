from pydantic import BaseModel

from app.schemas.intent import Intent
from app.schemas.route import Route
from app.schemas.user import UserProfile


class ChatRequest(BaseModel):
    session_id: str = "session_demo"
    user_id: str = "user_demo"
    message: str
    event_type: str = "user_message"


class AgentTraceStep(BaseModel):
    step: str
    label: str
    status: str


class ChatResponse(BaseModel):
    session_id: str
    message: str
    need_clarification: bool
    clarifying_question: str | None = None
    intent: Intent | None = None
    user_profile: UserProfile | None = None
    routes: list[Route]
    agent_trace: list[AgentTraceStep]

