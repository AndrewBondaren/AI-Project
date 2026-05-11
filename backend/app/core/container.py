from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from app.application.llm.engine.dag.DAGExecutor import DAGExecutor
from app.application.llm.engine.llmExecutionEngine import llmExecutionEngine

from app.application.llm.router import LLMRouter
from app.application.chat.chatService import ChatService

from app.core.config import settings


class Container:

    def __init__(self):

        self._qwen_client = None
        self._openai_client = None
        self._anthropic_client = None

        self._llm_router = None

        self._chat_service = None

        self._graph_registry = None

    def graph_registry(self):
        if self._graph_registry is None:
            self._graph_registry = {}
        return self._graph_registry

    # =====================================================
    # CLIENTS
    # =====================================================

    def qwen_client(self):

        if self._qwen_client is None:

            self._qwen_client = QwenClient(
                base_url=settings.QWEN_BASE_URL,
                api_key=settings.QWEN_API_KEY
            )

        return self._qwen_client

    def openai_client(self):

        if self._openai_client is None:

            self._openai_client = OpenAIClient(
                base_url=settings.OPENAI_BASE_URL,
                api_key=settings.OPENAI_API_KEY
            )

        return self._openai_client

    def anthropic_client(self):

        if self._anthropic_client is None:

            self._anthropic_client = AnthropicClient(
                base_url=settings.ANTHROPIC_BASE_URL,
                api_key=settings.ANTHROPIC_API_KEY
            )

        return self._anthropic_client

    # =====================================================
    # ROUTERS
    # =====================================================

    def llm_router(self):

        if self._llm_router is None:

            self._llm_router = LLMRouter(
                qwen_client=self.qwen_client(),
                openai_client=self.openai_client(),
                anthropic_client=self.anthropic_client()
            )

        return self._llm_router

    # =====================================================
    # SERVICES
    # =====================================================

    def chat_service(self):

        if self._chat_service is None:

            router = self.llm_router()
            graphs = self.graph_registry()

            executor = DAGExecutor()

            if router is None:
                raise RuntimeError("Router not initialized")

            if graphs is None:
                raise RuntimeError("Graph registry not initialized")

            executor = DAGExecutor()

        llm_engine = llmExecutionEngine(
            executor=executor,
            graph_registry=graphs
        )

        self._chat_service = ChatService(
            llm_engine=llm_engine
        )

        return self._chat_service