from __future__ import annotations

import asyncio

from app.config import settings
from app.llm import openai_client
from app.llm.openai_client import OpenAIClient


def test_openai_client_uses_configured_proxy(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeAsyncClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

    original_key = settings.openai_api_key
    original_proxy = settings.llm_proxy_url
    settings.openai_api_key = "test-key"
    settings.llm_proxy_url = "http://127.0.0.1:7897"
    monkeypatch.setattr(openai_client.httpx, "AsyncClient", FakeAsyncClient)
    try:
        asyncio.run(OpenAIClient().complete([{"role": "user", "content": "ping"}], json_mode=False))
    finally:
        settings.openai_api_key = original_key
        settings.llm_proxy_url = original_proxy

    assert captured["proxy"] == "http://127.0.0.1:7897"
