from fastapi import APIRouter

from app.agent.orchestrator import AgentOrchestrator
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])
orchestrator = AgentOrchestrator()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await orchestrator.handle_message(request)

