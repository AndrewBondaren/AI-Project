from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from app.application.llm.router import LLMRouter
from app.application.chat.chatService import ChatService

from app.application.engine.dag.dagExecutor import DAGExecutor
from app.application.engine.llmExecutionEngine import LLMExecutionEngine
from app.application.engine.graphs.graphCompiler import GraphCompiler
from app.application.engine.execution.llmNodeExecutor import LLMNodeExecutor
from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.prompt.promptCompiler import PromptCompiler
from app.application.engine.prompt.promptAggregator import PromptAggregator
from app.application.engine.prompt.promptAssambler import PromptAssembler
from app.application.engine.prompt.dslRegistry import DSLRegistry
from app.application.engine.prompt.dslAggregator import DSLAggregator
from app.application.engine.validation.llmValidator import LLMValidator
from app.application.engine.repair.repairOrchestrator import RepairOrchestrator
from app.application.engine.repair.repairBuilder import RepairBuilder
from app.application.engine.repair.patchApplier import PatchApplier
from app.application.engine.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.rules.ruleEngine import RuleEngine
from app.application.engine.rules.ruleCompiler import RuleCompiler
from app.application.engine.rules.ruleHandlerRegistry import RuleHandlerRegistry
from app.application.engine.rules.taskRuleHandler import TaskRuleHandler

from app.core.config import settings


class Container:

    def __init__(self):
        # CLIENTS
        self._qwen_client = None
        self._openai_client = None
        self._anthropic_client = None

        # ROUTING
        self._llm_router = None

        # RULES
        self._rule_handler_registry = None
        self._rule_compiler = None
        self._rule_engine = None

        # GRAPH
        self._graph_compiler = None

        # EXECUTION
        self._dag_executor = None
        self._llm_node_executor = None
        self._python_node_executor = None

        # PROMPT
        self._dsl_registry = None
        self._dsl_aggregator = None
        self._prompt_assembler = None
        self._prompt_aggregator = None
        self._prompt_compiler = None

        # VALIDATION & REPAIR
        self._validator = None
        self._repair_orchestrator = None

        # ENGINE & SERVICES
        self._llm_engine = None
        self._chat_service = None

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
    # ROUTING
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
    # RULES
    # =====================================================

    def rule_handler_registry(self):
        if self._rule_handler_registry is None:
            registry = RuleHandlerRegistry()
            registry.register("task", TaskRuleHandler())
            self._rule_handler_registry = registry
        return self._rule_handler_registry

    def rule_compiler(self):
        if self._rule_compiler is None:
            self._rule_compiler = RuleCompiler(
                registry=self.rule_handler_registry()
            )
        return self._rule_compiler

    def rule_engine(self):
        if self._rule_engine is None:
            self._rule_engine = RuleEngine()
        return self._rule_engine

    # =====================================================
    # GRAPH
    # =====================================================

    def graph_compiler(self):
        if self._graph_compiler is None:
            self._graph_compiler = GraphCompiler(
                rule_engine=self.rule_engine(),
                rule_compiler=self.rule_compiler()
            )
        return self._graph_compiler

    # =====================================================
    # EXECUTION
    # =====================================================

    def llm_node_executor(self):
        if self._llm_node_executor is None:
            self._llm_node_executor = LLMNodeExecutor(
                router=self.llm_router()
            )
        return self._llm_node_executor

    def python_node_executor(self):
        if self._python_node_executor is None:
            self._python_node_executor = PythonNodeExecutor()
        return self._python_node_executor

    def executors(self) -> dict:
        return {
            LLMNodeExecutor: self.llm_node_executor(),
            PythonNodeExecutor: self.python_node_executor()
        }

    def dag_executor(self):
        if self._dag_executor is None:
            self._dag_executor = DAGExecutor(
                validator=self.validator(),
                repair_orchestrator=self.repair_orchestrator()
            )
        return self._dag_executor

    # =====================================================
    # PROMPT
    # =====================================================

    def dsl_registry(self):
        if self._dsl_registry is None:
            self._dsl_registry = DSLRegistry(base_path="app/dsl")
        return self._dsl_registry

    def dsl_aggregator(self):
        if self._dsl_aggregator is None:
            self._dsl_aggregator = DSLAggregator()
        return self._dsl_aggregator

    def prompt_assembler(self):
        if self._prompt_assembler is None:
            self._prompt_assembler = PromptAssembler()
        return self._prompt_assembler

    def prompt_aggregator(self):
        if self._prompt_aggregator is None:
            self._prompt_aggregator = PromptAggregator()
        return self._prompt_aggregator

    def prompt_compiler(self):
        if self._prompt_compiler is None:
            self._prompt_compiler = PromptCompiler(
                dsl_registry=self.dsl_registry(),
                assembler=self.prompt_assembler()
            )
        return self._prompt_compiler

    # =====================================================
    # VALIDATION & REPAIR
    # =====================================================

    def validator(self):
        if self._validator is None:
            self._validator = LLMValidator()
        return self._validator

    def repair_orchestrator(self):
        if self._repair_orchestrator is None:
            self._repair_orchestrator = RepairOrchestrator(
                router=self.llm_router(),
                validator=self.validator(),
                builder=RepairBuilder(),
                applier=PatchApplier(),
                projector=DSLFailureProjector()
            )
        return self._repair_orchestrator

    # =====================================================
    # ENGINE
    # =====================================================

    def llm_engine(self):
        if self._llm_engine is None:
            self._llm_engine = LLMExecutionEngine(
                dag_executor=self.dag_executor(),
                graph_compiler=self.graph_compiler(),
                router=self.llm_router(),
                prompt_aggregator=self.prompt_aggregator(),
                prompt_compiler=self.prompt_compiler(),
                dsl_aggregator=self.dsl_aggregator(),
                validator=self.validator(),
                repair_orchestrator=self.repair_orchestrator(),
                executors=self.executors()
            )
        return self._llm_engine

    # =====================================================
    # SERVICES
    # =====================================================

    def chat_service(self):
        if self._chat_service is None:
            self._chat_service = ChatService(
                llm_engine=self.llm_engine()
            )
        return self._chat_service