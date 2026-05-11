from typing import Protocol
from app.application.llm.models import ChatMessage


class BaseLLMClient(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False
    ) -> str:
        ...