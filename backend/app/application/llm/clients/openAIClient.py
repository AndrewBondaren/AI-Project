from openai import AsyncOpenAI

from app.application.llm.models import ChatMessage, normalize_messages


class OpenAIClient:

    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False,
        response_format_schema: dict | None = None,
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

        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in normalized],
            stream=stream,
            **kwargs,
        )

        return response.choices[0].message.content
