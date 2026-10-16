"""LLM clients and routing wiring."""

from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from app.application.llm.router import LLMRouter
from app.core.appSettings import app_settings


class LlmWiring:
    """LLM client singletons and the provider router."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._qwen_client = None
        self._openai_client = None
        self._anthropic_client = None
        self._llm_router = None

    def invalidate_clients(self) -> None:
        self._qwen_client      = None
        self._openai_client    = None
        self._anthropic_client = None
        self._llm_router       = None

    def qwen_client(self):
        if self._qwen_client is None:
            self._qwen_client = QwenClient(
                base_url=app_settings.qwen_base_url,
                api_key=app_settings.qwen_api_key,
                streaming=app_settings.llm_streaming,
            )
        return self._qwen_client

    def openai_client(self):
        if self._openai_client is None:
            self._openai_client = OpenAIClient(
                base_url=app_settings.openai_base_url,
                api_key=app_settings.openai_api_key,
                streaming=app_settings.llm_streaming,
            )
        return self._openai_client

    def anthropic_client(self):
        if self._anthropic_client is None:
            self._anthropic_client = AnthropicClient(
                base_url=app_settings.anthropic_base_url,
                api_key=app_settings.anthropic_api_key,
                streaming=app_settings.llm_streaming,
            )
        return self._anthropic_client

    def llm_router(self):
        if self._llm_router is None:
            self._llm_router = LLMRouter(
                qwen_client=self.qwen_client(),
                openai_client=self.openai_client(),
                anthropic_client=self.anthropic_client()
            )
        return self._llm_router
