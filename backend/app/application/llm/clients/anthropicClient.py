import time
import anthropic

from app.application.llm.models import ChatMessage, normalize_messages
from app.application.events.eventBus import emit
from app.application.events.sseEvents import ThinkingEvent
from app.core.appSettings import app_settings


def _now_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


class AnthropicClient:

    def __init__(self, base_url: str | None, api_key: str | None, streaming: bool = True):
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        if api_key:
            kwargs["api_key"] = api_key
        self.client    = anthropic.AsyncAnthropic(**kwargs)
        self.streaming = streaming

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        response_format_schema: dict | None = None,
        enable_thinking: bool = False,
        node_id: str = "unknown",
    ) -> str:
        normalized = normalize_messages(messages)
        payload = [{"role": m.role, "content": m.content} for m in normalized]

        if self.streaming:
            return await self._chat_streaming(payload, model, node_id, enable_thinking)
        return await self._chat_full(payload, model, enable_thinking)

    # ------------------------------------------------------------------

    async def _chat_full(self, messages: list[dict], model: str, enable_thinking: bool = False) -> str:
        kwargs = {}
        if enable_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": app_settings.anthropic_thinking_budget}
        response = await self.client.messages.create(
            model=model,
            max_tokens=2048,
            messages=messages,
            **kwargs,
        )
        return response.content[0].text

    async def _chat_streaming(
        self, messages: list[dict], model: str, node_id: str, enable_thinking: bool = False
    ) -> str:
        start         = time.monotonic()
        thinking_text = ""
        response_text = ""
        think_emitted = False

        kwargs = {}
        if enable_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": app_settings.anthropic_thinking_budget}

        async with self.client.messages.stream(
            model=model,
            max_tokens=2048,
            messages=messages,
            **kwargs,
        ) as stream:
            async for event in stream:
                etype = getattr(event, "type", None)

                if etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", None)

                    if dtype == "thinking_delta":
                        thinking_text += getattr(delta, "thinking", "")

                    elif dtype == "text_delta":
                        response_text += getattr(delta, "text", "")

                elif etype == "content_block_stop":
                    # emit once thinking block closes
                    if thinking_text and not think_emitted:
                        await emit(ThinkingEvent(
                            node_id=node_id,
                            text=thinking_text.strip(),
                            elapsed_ms=_now_ms(start),
                        ))
                        think_emitted = True

        return response_text
