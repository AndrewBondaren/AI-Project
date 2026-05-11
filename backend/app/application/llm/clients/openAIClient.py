from openai import AsyncOpenAI
from app.application.llm.models import ChatMessage


class OpenAIClient:

    def __init__(self, base_url: str, api_key: str):
        self.client = AsyncOpenAI(base_url=base_url,api_key = api_key)

    async def chat(self, messages: list[ChatMessage], model: str, stream: bool = False) -> str:


        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            stream=stream
        )

        return response.choices[0].message.content