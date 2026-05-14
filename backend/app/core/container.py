from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from backend.app.application.engine.dag.DAGExecutor import DAGExecutor
from backend.app.application.engine.llmExecutionEngine import llmExecutionEngine
from backend.app.application.engine.nodes.pojo.PythonNodeSpec import PythonNode
from backend.app.application.engine.nodes.pojo.LLMNodeSpec import LLMNode
from backend.app.application.engine.nodes.nodeExecutorRegistry import NodeExecutorRegistry
from app.application.llm.router import LLMRouter
from app.application.chat.chatService import ChatService
from backend.app.application.engine.execution.llmNodeExecutor import LLMNodeExecutor
from backend.app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from backend.app.application.engine.prompt.promptCompiler import PromptCompiler
from backend.app.application.engine.prompt.promptAggregator import PromptAggregator
from backend.app.application.engine.prompt.promptAssambler import PromptAssembler
from backend.app.application.engine.prompt.dslRegistry import DSLRegistry
from backend.app.application.engine.prompt.dslAggregator import DSLAggregator
from backend.app.application.engine.validation.llmValidator import LLMValidator
from backend.app.application.engine.repair.repairOrchestrator import RepairOrchestrator
from backend.app.application.engine.repair.repairBuilder import RepairBuilder
from backend.app.application.engine.repair.patchApplier import PatchApplier
from backend.app.application.engine.repair.dslFailureProjector import DSLFailureProjector

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
        self._repair_orchestrator = None
        #self._execution_contract_registry = None

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
    
    #def execution_contract_registry(self):

     #   if self._execution_contract_registry is None:
     #       self._execution_contract_registry = ExecutionContractRegistry()

     #   return self._execution_contract_registry
    

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
    
    def repair_orchestrator(self):
        if self._repair_orchestrator is None:
            self._repair_orchestrator = RepairOrchestrator(
                self.llm_router(),
                self.validator(),
                RepairBuilder(),
                PatchApplier(),
                DSLFailureProjector()
            )
        return self._repair_orchestrator
    
    def llm_engine(self):
        if self._llm_engine is None:
            self._llm_engine = llmExecutionEngine(
                node_registry=bootstrap.get_node_registry(),
                dag_executor=self.dag_executor(),
                router=self.llm_router(),
                node_executor_registry=self.node_executor_registry(),
                prompt_aggregator=self.prompt_aggregator(),
                prompt_compiler=self.prompt_compiler(),
                dsl_aggregator=self.dsl_aggregator(),
                validator=self.validator(),
                dsl_resolver=self.dsl_registry(),
                repair_orchestrator=self.repair_orchestrator()
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