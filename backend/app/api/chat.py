import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent.orchestrator import AgentOrchestrator
from app.schemas.chat import AgentTraceStep
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])
orchestrator = AgentOrchestrator()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await orchestrator.handle_message(request)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def emit_progress(step: AgentTraceStep) -> None:
            await queue.put({"type": "progress", "step": step.model_dump()})

        async def run_agent() -> None:
            try:
                response = await orchestrator.handle_message(request, progress_callback=emit_progress)
                await queue.put({"type": "final", "response": response.model_dump()})
            except Exception as exc:
                await queue.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            finally:
                await queue.put({"type": "done"})

        task = asyncio.create_task(run_agent())
        try:
            while True:
                event = await queue.get()
                if event["type"] == "done":
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
