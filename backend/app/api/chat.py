import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent.v2.runtime import AgentRuntimeRouter
from app.schemas.chat import AgentTraceStep
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.route import Route

router = APIRouter(tags=["chat"])
orchestrator = AgentRuntimeRouter()


async def enqueue_stream_event(queue: asyncio.Queue[dict], event: dict) -> None:
    await queue.put(event)
    await asyncio.sleep(0)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await orchestrator.handle_message(request)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        queue: asyncio.Queue[dict] = asyncio.Queue()

        async def emit_progress(step: AgentTraceStep) -> None:
            await enqueue_stream_event(queue, {"type": "progress", "step": step.model_dump()})

        async def emit_routes(routes: list[Route]) -> None:
            await enqueue_stream_event(queue, {"type": "routes", "routes": [route.model_dump() for route in routes]})

        async def run_agent() -> None:
            try:
                response = await orchestrator.handle_message(request, progress_callback=emit_progress, routes_callback=emit_routes)
                await enqueue_stream_event(queue, {"type": "final", "response": response.model_dump()})
            except Exception as exc:
                await enqueue_stream_event(queue, {"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            finally:
                await enqueue_stream_event(queue, {"type": "done"})

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
