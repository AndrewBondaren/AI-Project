import json
import logging
import httpx

from app.application.llm.models import ChatMessage, normalize_messages

logger = logging.getLogger(__name__)

_THINK_CLOSE = "</think>"



class QwenClient:

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        response_format_schema: dict | None = None,
        enable_thinking: bool = False,
    ) -> str:

        normalized = normalize_messages(messages)

        messages_payload = [{"role": m.role, "content": m.content} for m in normalized]

        payload = {
            "model": model,
            "messages": messages_payload,
            "stream": stream,
        }

        for msg in messages_payload:
            logger.debug("qwen_request model=%s role=%s content=%s", model, msg["role"], msg["content"])

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )

        response.raise_for_status()

        data = response.json()

        content: str = data["choices"][0]["message"]["content"] or ""
        if _THINK_CLOSE in content:
            content = content[content.rfind(_THINK_CLOSE) + len(_THINK_CLOSE):]
        result = content.strip()
        logger.debug("qwen_result=%s", result)
        return result