from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.llm.base import LLMClient


logger = logging.getLogger("app.llm.openai")


class OpenAIClient(LLMClient):
    async def complete(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = True) -> dict:
        api_key = settings.ofox_api_key if "ofox.ai" in settings.openai_base_url else settings.openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        payload: dict = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools

        url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
        logger.info(
            "LLM request provider=openai model=%s url=%s messages=%s tools=%s json_mode=%s",
            settings.openai_model,
            url,
            len(messages),
            len(tools or []),
            json_mode,
        )

        async with httpx.AsyncClient(timeout=30, proxy=settings.llm_proxy_url or None) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                logger.info("LLM response provider=openai status=%s", response.status_code)
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info("LLM content provider=openai content=%s", self._preview(content))
                return data
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "LLM HTTP error provider=openai status=%s body=%s",
                    exc.response.status_code,
                    self._preview(exc.response.text),
                )
                raise

    def _preview(self, value: str, limit: int = 800) -> str:
        return value if len(value) <= limit else f"{value[:limit]}..."
