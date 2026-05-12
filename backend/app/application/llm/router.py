from app.application.llm.clients.baseClient import BaseLLMClient

class LLMRouter:

    def __init__(self, qwen_client, openai_client, anthropic_client):
        self.qwen = qwen_client
        self.openai = openai_client
        self.anthropic = anthropic_client

    def get(self, provider: str) -> BaseLLMClient:

        if provider == "qwen":
            return self.qwen

        if provider == "openai":
            return self.openai

        if provider == "anthropic":
            return self.anthropic

        raise ValueError(f"Unknown provider: {provider}")