from app.infrastructure.llm.qwenClient import QwenClient


class LLMRouter:
    def __init__(self, qwen: QwenClient):
        self.qwen = qwen

    async def generate(self, messages: list[dict]):
        # пока только Qwen, но ты уже готов к расширению (GPT / Claude)
        return await self.qwen.chat(messages)