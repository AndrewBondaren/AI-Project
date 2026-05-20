from typing import Protocol
from app.application.llm.models import ChatMessage


class BaseLLMClient(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        response_format_schema: dict | None = None,
        enable_thinking: bool = False,
        node_id: str = "unknown",
        cancel_token=None,
    ) -> str:
        ...
