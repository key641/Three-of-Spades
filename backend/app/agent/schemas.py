from pydantic import BaseModel, Field

from app.schemas.chat import AgentTraceStep
from app.schemas.intent import Intent
from app.schemas.poi import POI
from app.schemas.route import Route
from app.schemas.user import UserProfile


class ToolCallResult(BaseModel):
    tool_name: str
    success: bool
    payload: dict


class ChatTurn(BaseModel):
    role: str
    content: str


class SessionState(BaseModel):
    session_id: str
    recent_messages: list[ChatTurn] = Field(default_factory=list)
    last_intent: Intent | None = None
    current_routes: list[Route] = Field(default_factory=list)
    user_profile: UserProfile | None = None


class AgentState(BaseModel):
    session_id: str
    message: str
    intent: Intent | None = None
    user_profile: UserProfile | None = None
    candidate_pois: list[POI] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    agent_trace: list[AgentTraceStep] = Field(default_factory=list)
