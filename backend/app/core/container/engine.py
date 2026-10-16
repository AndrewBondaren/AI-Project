"""Engine wiring: rules, graphs, prompt, validation/repair, execution."""

from app.application.engine.dag.dagExecutor import DAGExecutor
from app.application.engine.llmExecutionEngine import LLMExecutionEngine
from app.application.engine.responseResolver import ResponseResolver
from app.application.engine.graphs.graphCompiler import GraphCompiler
from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.execution.nodeRunner import NodeRunner
from app.application.engine.prompt.dslRegistry import DSLRegistry
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
import app.application.engine.nodes  # noqa: F401

from app.application.cancellation.snapshotStore import snapshot_store


class EngineWiring:
    """DSL/LLM execution engine wiring: rules → graph → executors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rule_handler_registry = None
        self._rule_compiler = None
        self._rule_engine = None
        self._graph_compiler = None
        self._node_runner = None
        self._python_node_executor = None
        self._llm_aggregate_executor = None
        self._dag_executor = None
        self._dsl_registry = None
        self._dsl_resolver = None
        self._payload_builder = None
        self._node_validator = None
        self._llm_validator = None
        self._repair_orchestrator = None
        self._patch_applier = None
        self._llm_engine = None
        self._response_resolver = None

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
            compiler = GraphCompiler(
                rule_engine=self.rule_engine(),
                rule_compiler=self.rule_compiler()
            )
            compiler.precompile()
            self._graph_compiler = compiler
        return self._graph_compiler

    # =====================================================
    # PROMPT
    # =====================================================

    def dsl_registry(self):
        if self._dsl_registry is None:
            self._dsl_registry = DSLRegistry(base_path="app/dsl")
        return self._dsl_registry

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

    def response_resolver(self):
        if self._response_resolver is None:
            self._response_resolver = ResponseResolver()
        return self._response_resolver

    def llm_engine(self):
        if self._llm_engine is None:
            self._llm_engine = LLMExecutionEngine(
                dag_executor=self.dag_executor(),
                graph_compiler=self.graph_compiler(),
                patch_applier=self.patch_applier(),
                executors=self.executors(),
                snapshot_store=snapshot_store,
                response_resolver=self.response_resolver(),
                repositories={
                    "scene_repo":                  self.scene_repository(),
                    "location_repo":               self.location_repository(),
                    "player_repo":                 self.player_repository(),
                    "npc_repo":                    self.npc_repository(),
                    "world_repo":                  self.world_repository(),
                    "state_repo":                  self.state_repository(),
                    "map_cell_repo":               self.map_cell_repository(),
                    "map_cell_service":            self.map_cell_service(),
                    "connection_persist_service":  self.connection_persist_service(),
                    "settlement_persist_service":  self.settlement_persist_service(),
                },
            )
        return self._llm_engine
