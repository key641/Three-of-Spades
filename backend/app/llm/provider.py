from app.config import settings
from app.llm.base import LLMClient
from app.llm.deepseek_client import DeepSeekClient
from app.llm.openai_client import OpenAIClient


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "deepseek":
        return DeepSeekClient()
    return OpenAIClient()

