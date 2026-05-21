import asyncio
import unittest
from unittest.mock import AsyncMock

from app.agent.message_router import MessageIntentType, MessageRouter
from app.agent.schemas import SessionState


class MessageRouterTest(unittest.TestCase):
    def test_llm_router_classifies_route_detail_question(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": '{"intent_type":"route_detail_question","confidence":0.91,"references_previous_route":true,"detail_type":"transport_between_stops"}'
                            }
                        }
                    ]
                }
            )

            result = await MessageRouter(llm_client).classify(
                "就你刚刚生成的方案，那俩地之间怎么过去",
                SessionState(session_id="s1"),
            )

            self.assertEqual(result.intent_type, MessageIntentType.ROUTE_DETAIL_QUESTION)
            self.assertTrue(result.references_previous_route)
            self.assertEqual(result.detail_type, "transport_between_stops")

        asyncio.run(run_case())

    def test_router_falls_back_to_route_detail_when_llm_fails(self) -> None:
        async def run_case() -> None:
            llm_client = AsyncMock()
            llm_client.complete = AsyncMock(side_effect=RuntimeError("llm down"))

            result = await MessageRouter(llm_client).classify(
                "两个地点之间我怎么过去",
                SessionState(session_id="s1"),
            )

            self.assertEqual(result.intent_type, MessageIntentType.ROUTE_DETAIL_QUESTION)
            self.assertTrue(result.references_previous_route)

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
