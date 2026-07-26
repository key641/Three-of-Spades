from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = True) -> dict:
        raise NotImplementedError
