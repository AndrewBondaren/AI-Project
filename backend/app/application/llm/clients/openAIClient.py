import json
import logging

from openai import AsyncOpenAI

from app.application.llm.models import ChatMessage, normalize_messages

logger = logging.getLogger(__name__)


class OpenAIClient:

    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        response_format_schema: dict | None = None,
        enable_thinking: bool = False,
    ) -> str:

        normalized = normalize_messages(messages)

        kwargs = {}
        if response_format_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "nodes_response",
                    "strict": True,
                    "schema": response_format_schema,
                },
            }

        messages_payload = [{"role": m.role, "content": m.content} for m in normalized]

        def _fmt(msgs):
            out = []
            for m in msgs:
                try:
                    content = json.loads(m["content"])
                except (json.JSONDecodeError, TypeError):
                    content = m["content"]
                out.append({"role": m["role"], "content": content})
            return out

        logger.debug("openai_request model=%s messages=%s", model, json.dumps(_fmt(messages_payload), ensure_ascii=False, separators=(",", ":")))

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages_payload,
            stream=stream,
            **kwargs,
        )

        result = response.choices[0].message.content
        logger.debug("openai_response model=%s result=%s", model, result)
        return result
