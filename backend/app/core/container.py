# core/container.py

from infrastructure.llm.qwenClient import QwenClient
from infrastructure.llm.router import LLMRouter
from core.config import settings


def create_llm_router():
    client = QwenClient(
        base_url=settings.QWEN_BASE_URL,
        api_key=settings.QWEN_API_KEY
    )

    return LLMRouter(client)