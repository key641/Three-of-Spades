from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        raise NotImplementedError

