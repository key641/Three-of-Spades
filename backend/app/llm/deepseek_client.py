from app.llm.base import LLMClient


class DeepSeekClient(LLMClient):
    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        # TODO(A): wire DeepSeek OpenAI-compatible SDK call.
        return {"provider": "deepseek", "messages": messages, "tools": tools or []}

