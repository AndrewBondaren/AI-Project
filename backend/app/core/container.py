from app.infrastructure.llm.qwenClient import QwenClient
from app.infrastructure.llm.router import LLMRouter
from app.core.config import settings


def create_llm_router():
    client = QwenClient(
        base_url=settings.QWEN_BASE_URL,
        api_key=settings.QWEN_API_KEY
    )

    return LLMRouter(client)