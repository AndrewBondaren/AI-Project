from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from app.application.llm.engine.dag.DAGExecutor import DAGExecutor
from app.application.llm.engine.llmExecutionEngine import llmExecutionEngine
from app.application.llm.engine.nodes.pythonNode import PythonNode
from app.application.llm.engine.nodes.llmNode import LLMNode
from app.application.llm.engine.nodes.nodeExecutorRegistry import NodeExecutorRegistry
from app.application.llm.router import LLMRouter
from app.application.chat.chatService import ChatService
from app.application.llm.engine.execution.llmNodeExecutor import LLMNodeExecutor
from app.application.llm.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.llm.engine.prompt.promptCompiler import PromptCompiler
from app.application.llm.engine.prompt.promptAggregator import PromptAggregator
from app.application.llm.engine.prompt.promptAssambler import PromptAssembler
from app.application.llm.engine.prompt.dslRegistry import DSLRegistry
from app.application.llm.engine.prompt.dslAggregator import DSLAggregator
from app.application.llm.engine.validation import llmValidation

from app.core.config import settings


class Container:

    def __init__(self):

        self._qwen_client = None
        self._openai_client = None
        self._anthropic_client = None
        self._llm_router = None
        self._llm_engine = None
        self._dag_executor = None
        self._chat_service = None
        self._node_executor_registry = None
        self._dsl_registry = None
        self._prompt_compiler = None
        self._prompt_aggregator = None
        self._prompt_assembler = None
        self._dsl_aggregator = None
        self._validator = None


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
    
    def dsl_aggregator(self):
        if self._dsl_aggregator is None:
            self._dsl_aggregator = DSLAggregator()

        return self._dsl_aggregator

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
    
    def dag_executor(self):
        if self._dag_executor is None:
            self._dag_executor = DAGExecutor()
        return self._dag_executor
    
    def node_executor_registry(self):
        if self._node_executor_registry is None:
            self._node_executor_registry = NodeExecutorRegistry()
            self._node_executor_registry.register(
                LLMNode,
                LLMNodeExecutor(
                    router=self.llm_router()
                )
            )

            self._node_executor_registry.register(
                PythonNode,
                PythonNodeExecutor()
            )

        return self._node_executor_registry
    
    def dsl_registry(self):
        if self._dsl_registry is None:
            self._dsl_registry = DSLRegistry(base_path="app/dsl")
        return self._dsl_registry


    def prompt_aggregator(self):
        if self._prompt_aggregator is None:
            self._prompt_aggregator = PromptAggregator()
        return self._prompt_aggregator


    def prompt_assembler(self):
        if self._prompt_assembler is None:
            self._prompt_assembler = PromptAssembler()
        return self._prompt_assembler


    def prompt_compiler(self):
        if self._prompt_compiler is None:
            self._prompt_compiler = PromptCompiler(
                dsl_registry=self.dsl_registry(),
                assembler=self.prompt_assembler()
            )
        return self._prompt_compiler
    
    def validator(self):
        if self._validator is None:
            self._validator = LLMValidator()
        return self._validator
    
    def llm_engine(self):
        if self._llm_engine is None:
            self._llm_engine = llmExecutionEngine(
                dag_executor=self.dag_executor(),
                router=self.llm_router(),
                node_executor_registry=self.node_executor_registry(),
                prompt_aggregator=self.prompt_aggregator(),
                prompt_compiler=self.prompt_compiler(),
                dsl_aggregator=self.dsl_aggregator(),
                validator=self.validator()
            )

        return self._llm_engine

    # =====================================================
    # SERVICES
    # =====================================================

    def chat_service(self):
        if self._chat_service is None:
            self._chat_service = ChatService(
            llm_engine=self.llm_engine(),
        )
            
        return self._chat_service