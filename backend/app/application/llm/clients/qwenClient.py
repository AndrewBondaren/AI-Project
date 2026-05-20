import json
import logging
import time
import httpx

from app.application.llm.models import ChatMessage, normalize_messages
from app.application.events.eventBus import emit
from app.application.events.sseEvents import ThinkingEvent

logger = logging.getLogger(__name__)

_THINK_OPEN  = "<think>"
_THINK_CLOSE = "</think>"


def _now_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


class QwenClient:

    def __init__(self, base_url: str, api_key: str | None = None, streaming: bool = True):
        self.base_url  = base_url
        self.api_key   = api_key
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
        for m in normalized:
            try:
                content = json.loads(m.content)
            except Exception:
                content = m.content
            logger.debug("qwen_request", extra={"model": model, "role": m.role, "content": content})

        if self.streaming:
            result = await self._chat_streaming(normalized, model, node_id)
        else:
            result = await self._chat_full(normalized, model)

        try:
            result_obj = json.loads(result)
        except Exception:
            result_obj = result
        logger.debug("qwen_result", extra={"result": result_obj})
        return result

    # ------------------------------------------------------------------

    async def _chat_full(self, normalized: list[ChatMessage], model: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in normalized],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        response.raise_for_status()
        content: str = response.json()["choices"][0]["message"]["content"] or ""
        return self._strip_thinking(content)

    async def _chat_streaming(
        self, normalized: list[ChatMessage], model: str, node_id: str
    ) -> str:
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in normalized],
            "stream": True,
        }

        start       = time.monotonic()
        full        = ""
        think_emitted = False

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    token = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                    if not token:
                        continue

                    full += token

                    # emit ThinkingEvent once the thinking block closes
                    if not think_emitted and _THINK_CLOSE in full:
                        close_idx    = full.rfind(_THINK_CLOSE)
                        think_text   = full[:close_idx]
                        if think_text.startswith(_THINK_OPEN):
                            think_text = think_text[len(_THINK_OPEN):]
                        await emit(ThinkingEvent(
                            node_id=node_id,
                            text=think_text.strip(),
                            elapsed_ms=_now_ms(start),
                        ))
                        think_emitted = True

        return self._strip_thinking(full)

    @staticmethod
    def _strip_thinking(content: str) -> str:
        if _THINK_CLOSE in content:
            content = content[content.rfind(_THINK_CLOSE) + len(_THINK_CLOSE):]
        return content.strip()
