import json
import unittest
import asyncio

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api.chat import enqueue_stream_event
from app.main import app
from app.schemas.chat import AgentTraceStep, ChatRequest, ChatResponse


class FakeStreamingOrchestrator:
    async def handle_message(self, request: ChatRequest, progress_callback=None) -> ChatResponse:
        if progress_callback:
            await progress_callback(AgentTraceStep(step="route_message", label="识别为：补充需求 add_constraint", status="done"))
            await progress_callback(AgentTraceStep(step="apply_query_delta", label="保留 上海、2人；新增 吃饭节点", status="done"))
        return ChatResponse(
            session_id=request.session_id,
            message="我保留了上海、2人，并新增了吃饭节点。",
            need_clarification=False,
            intent=None,
            user_profile=None,
            routes=[],
            agent_trace=[
                AgentTraceStep(step="route_message", label="识别为：补充需求 add_constraint", status="done"),
                AgentTraceStep(step="apply_query_delta", label="保留 上海、2人；新增 吃饭节点", status="done"),
            ],
        )


class ChatStreamTest(unittest.TestCase):
    def test_enqueue_stream_event_yields_to_waiting_consumer(self) -> None:
        async def run_case() -> None:
            queue: asyncio.Queue[dict] = asyncio.Queue()
            consumed: list[dict] = []

            async def consume_once() -> None:
                consumed.append(await queue.get())

            consumer_task = asyncio.create_task(consume_once())
            await enqueue_stream_event(queue, {"type": "progress"})

            self.assertEqual(consumed, [{"type": "progress"}])
            await consumer_task

        asyncio.run(run_case())

    def test_chat_stream_emits_progress_before_final_response(self) -> None:
        original_orchestrator = chat_api.orchestrator
        chat_api.orchestrator = FakeStreamingOrchestrator()
        try:
            client = TestClient(app)
            with client.stream("POST", "/api/chat/stream", json={"message": "我还要吃饭"}) as response:
                self.assertEqual(response.status_code, 200)
                self.assertIn("application/x-ndjson", response.headers["content-type"])
                events = [json.loads(line) for line in response.iter_lines() if line]

            self.assertGreaterEqual(len(events), 3)
            self.assertEqual(events[0]["type"], "progress")
            self.assertEqual(events[0]["step"]["step"], "route_message")
            self.assertIn("补充需求", events[0]["step"]["label"])
            self.assertEqual(events[1]["type"], "progress")
            self.assertEqual(events[-1]["type"], "final")
            self.assertIn("新增了吃饭节点", events[-1]["response"]["message"])
        finally:
            chat_api.orchestrator = original_orchestrator


if __name__ == "__main__":
    unittest.main()
