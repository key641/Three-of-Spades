from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.llm.base import LLMClient


logger = logging.getLogger("app.llm.deepseek")


class DeepSeekClient(LLMClient):
    async def complete(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = True) -> dict:
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        payload: dict = {
            "model": settings.deepseek_model,
            "messages": messages,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools

        url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        logger.info(
            "LLM request provider=deepseek model=%s url=%s messages=%s tools=%s json_mode=%s",
            settings.deepseek_model,
            url,
            len(messages),
            len(tools or []),
            json_mode,
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {settings.deepseek_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                logger.info("LLM response provider=deepseek status=%s", response.status_code)
                response.raise_for_status()
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info("LLM content provider=deepseek content=%s", self._preview(content))
                return data
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "LLM HTTP error provider=deepseek status=%s body=%s",
                    exc.response.status_code,
                    self._preview(exc.response.text),
                )
                raise

    def _preview(self, value: str, limit: int = 800) -> str:
        return value if len(value) <= limit else f"{value[:limit]}..."
