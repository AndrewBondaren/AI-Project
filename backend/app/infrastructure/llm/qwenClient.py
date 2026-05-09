# infrastructure/llm/qwen_client.py

import httpx


class QwenClient:
    def __init__(self, base_url: str, api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key

    async def chat(self, messages: list[dict], temperature: float = 0.7):
        payload = {
            "messages": messages,
            "temperature": temperature,
        }

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers
            )

        response.raise_for_status()
        return response.json()