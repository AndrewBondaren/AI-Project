import anthropic


class AnthropicClient:

    def __init__(self, base_url: str | None, api_key: str | None):

        kwargs = {}

        if base_url:
            kwargs["base_url"] = base_url

        if api_key:
            kwargs["api_key"] = api_key

        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def generate(self, messages: list[dict], model: str) -> str:

        response = await self.client.messages.create(
            model=model,
            max_tokens=2048,
            messages=messages
        )

        return response.content[0].text