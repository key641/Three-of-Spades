from app.llm.base import LLMClient


class OpenAIClient(LLMClient):
    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        # TODO(A): wire real OpenAI SDK call.
        return {"provider": "openai", "messages": messages, "tools": tools or []}

