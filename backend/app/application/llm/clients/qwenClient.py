import httpx
from app.application.llm.models import ChatMessage


class QwenClient:

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        stream: bool = False
    ) -> str:

        payload = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "stream": stream
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"}
            )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]