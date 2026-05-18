from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from app.application.llm.router import LLMRouter
from app.application.chat.chatService import ChatService

from app.application.engine.dag.dagExecutor import DAGExecutor
from app.application.engine.llmExecutionEngine import LLMExecutionEngine
from app.application.engine.graphs.graphCompiler import GraphCompiler
from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.execution.NodeRunner import NodeRunner
from app.application.engine.prompt.dslRegistry import DSLRegistry
from app.application.engine.prompt.dslAggregator import DSLAggregator
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.validation.llmValidator import LLMValidator
from app.application.engine.validation.contractValidator import ContractValidator
from app.application.engine.validation.nodeValidator import NodeValidator
from app.application.engine.repair.repairOrchestrator import RepairOrchestrator
from app.application.engine.repair.repairBuilder import RepairBuilder
from app.application.engine.repair.patchApplier import PatchApplier
from app.application.engine.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.rules.ruleEngine import RuleEngine
from app.application.engine.rules.ruleCompiler import RuleCompiler
from app.application.engine.rules.ruleHandlerRegistry import RuleHandlerRegistry
from app.application.engine.rules.taskRuleHandler import TaskRuleHandler

# Импорт нод = их регистрация в NODE_REGISTRY
#import app.application.engine.nodes  # noqa: F401

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
        self._node_runner = None
        self._python_node_executor = None
        self._llm_aggregate_executor = None
        self._dag_executor = None

        # PROMPT
        self._dsl_registry = None
        self._dsl_aggregator = None
        self._dsl_resolver = None
        self._payload_builder = None

        # VALIDATION & REPAIR
        self._node_validator = None
        self._llm_validator = None
        self._repair_orchestrator = None
        self._patch_applier = None

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

    def dsl_resolver(self):
        if self._dsl_resolver is None:
            self._dsl_resolver = DSLResolver(
                dsl_registry=self.dsl_registry()
            )
        return self._dsl_resolver

    def payload_builder(self):
        if self._payload_builder is None:
            self._payload_builder = LLMGroupPayloadBuilder(
                dsl_resolver=self.dsl_resolver()
            )
        return self._payload_builder

    # =====================================================
    # VALIDATION
    # =====================================================

    def node_validator(self):
        if self._node_validator is None:
            self._node_validator = NodeValidator()
        return self._node_validator

    def llm_validator(self):
        if self._llm_validator is None:
            self._llm_validator = LLMValidator(
                contract_validator=ContractValidator(),
                node_validator=self.node_validator()
            )
        return self._llm_validator

    # =====================================================
    # REPAIR
    # =====================================================

    def patch_applier(self):
        if self._patch_applier is None:
            self._patch_applier = PatchApplier()
        return self._patch_applier

    def repair_orchestrator(self):
        if self._repair_orchestrator is None:
            self._repair_orchestrator = RepairOrchestrator(
                dsl_resolver=self.dsl_resolver(),
                repair_builder=RepairBuilder(
                    payload_builder=self.payload_builder(),
                    failure_projector=DSLFailureProjector()
                ),
                llm_validator=self.llm_validator()
            )
        return self._repair_orchestrator

    # =====================================================
    # EXECUTION
    # =====================================================

    def python_node_executor(self):
        if self._python_node_executor is None:
            self._python_node_executor = PythonNodeExecutor()
        return self._python_node_executor

    def llm_aggregate_executor(self):
        if self._llm_aggregate_executor is None:
            self._llm_aggregate_executor = LLMAggregateExecutor(
                payload_builder=self.payload_builder(),
                llm_validator=self.llm_validator(),
                dsl_resolver=self.dsl_resolver(),
                dsl_registry=self.dsl_registry(),
                repair_orchestrator=self.repair_orchestrator(),
                router=self.llm_router()
            )
        return self._llm_aggregate_executor

    def node_runner(self):
        if self._node_runner is None:
            self._node_runner = NodeRunner(
                node_validator=self.node_validator()
            )
        return self._node_runner

    def dag_executor(self):
        if self._dag_executor is None:
            self._dag_executor = DAGExecutor(
                node_runner=self.node_runner(),
                llm_aggregate_executor=self.llm_aggregate_executor()
            )
        return self._dag_executor

    def executors(self) -> dict:
        return {
            PythonNodeExecutor: self.python_node_executor(),
        }

    # =====================================================
    # ENGINE
    # =====================================================

    def llm_engine(self):
        if self._llm_engine is None:
            self._llm_engine = LLMExecutionEngine(
                dag_executor=self.dag_executor(),
                graph_compiler=self.graph_compiler(),
                patch_applier=self.patch_applier(),
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