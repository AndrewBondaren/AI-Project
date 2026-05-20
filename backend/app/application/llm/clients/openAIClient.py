import json
import logging

from openai import AsyncOpenAI

from app.application.llm.models import ChatMessage, normalize_messages

logger = logging.getLogger(__name__)


class OpenAIClient:

    def __init__(self, base_url: str, api_key: str, streaming: bool = True):
        self.client    = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.streaming = streaming

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        response_format_schema: dict | None = None,
        enable_thinking: bool = False,
        node_id: str = "unknown",
    ) -> str:
        normalized     = normalize_messages(messages)
        messages_payload = [{"role": m.role, "content": m.content} for m in normalized]

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

        logger.debug("openai_request model=%s messages=%s", model,
                     json.dumps(self._fmt(messages_payload), ensure_ascii=False, separators=(",", ":")))

        if self.streaming:
            result = await self._chat_streaming(messages_payload, model, kwargs)
        else:
            result = await self._chat_full(messages_payload, model, kwargs)

        logger.debug("openai_response model=%s result=%s", model, result)
        return result

    # ------------------------------------------------------------------

    async def _chat_full(self, messages_payload: list[dict], model: str, kwargs: dict) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages_payload,
            stream=False,
            **kwargs,
        )
        return response.choices[0].message.content

    async def _chat_streaming(
        self, messages_payload: list[dict], model: str, kwargs: dict
    ) -> str:
        result = ""
        async for chunk in await self.client.chat.completions.create(
            model=model,
            messages=messages_payload,
            stream=True,
            **kwargs,
        ):
            token = chunk.choices[0].delta.content
            if token:
                result += token
        return result

    @staticmethod
    def _fmt(msgs: list[dict]) -> list[dict]:
        out = []
        for m in msgs:
            try:
                content = json.loads(m["content"])
            except (json.JSONDecodeError, TypeError):
                content = m["content"]
            out.append({"role": m["role"], "content": content})
        return out
