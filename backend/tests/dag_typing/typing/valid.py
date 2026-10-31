"""Positive static API probes, including request-local factories and ports."""

from typing import Never
from typing import assert_type

from app.dataModel.engine.dag.errors.nodeError import NodeError

from pydantic import BaseModel

from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.runtime.prompt.pojo.nodeSection import NodeSection
from app.application.engine.runtime.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.runtime.prompt.pojo.llmRepairPayload import LLMRepairPayload
from app.application.engine.runtime.repair.repairBuilder import RepairBuilder
from app.application.engine.runtime.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.runtime.dag.executionPlan import LLMGroup
from app.application.engine.runtime.llmExecutionEngine import LLMExecutionEngine
from app.application.engine.runtime.responseResolver import ResponseResolver
from app.application.engine.contracts.executionBindings import ExecutionCursor, LifecycleBinding, PassStage
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.diagnostics.dagLog import emit
from app.application.engine.diagnostics.events import ReplanDiagnostic
from app.application.engine.contracts.executionBindings import (
    ExecutionBindings, ResolveResult, ResponseBinding, SnapshotExtension, TransitionBinding,
)
from app.application.engine.contracts.nodeContract import NodeContract, OutputLifecycle
from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.nodeTypes.compiledNode import CompiledNode
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.registration.nodeRegistry import NodeRegistry, register_llm, register_python
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision, NodeOutcome
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.llmValidator import LLMValidator
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, ExecutionId, ExecutionIdentity, NodeId, PlanRevision
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence, OutputRecord
from app.dataModel.engine.dag.diagnostics import CancellationRequest, CancellationSource, ExecutionEventCode, ExecutionSeverity, OutputRequirement
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase
from tests.dag_typing.fixtures import (
    CompositeOutput, FakeExecutor, FakeReadView, LEAF_CONTRACT, LeafOutput, NodeInput, OtherInput,
    OPTIONAL_COMPOSITE, REQUIRED_LEAF, TypedLLMNode, TypedPythonNode,
    RecordingValidator, identity,
    ERROR_CONTRACT, TestNodeError, TestOtherError, TypedErrorNode, GraphBindings,
)


class Response:
    def resolve(self, view: DAGReadView) -> ResolveResult[LeafOutput]:
        return ResolveResult(ok=True, data=view.require(REQUIRED_LEAF))


class Transition:
    def transition(self, view: DAGReadView) -> TaskType | None:
        return None


class Extension:
    snapshot_type = LeafOutput
    contract_id = ContractId("test.extension")
    version = ContractVersion("1")

    def capture(self) -> LeafOutput:
        return LeafOutput(value=1)

    async def restore(self, value: LeafOutput) -> None:
        pass

    async def validate_restored(self, value: LeafOutput) -> None:
        pass


class Factory:
    def __init__(self, node: object) -> None:
        self._node = node

    def make_node[I: BaseModel, O: BaseModel, E: NodeError](
        self, registration: NodeRegistration[I, O, E],
    ) -> BaseNode[I, O, E]:
        # The fake integration supplies a request-local, already constructed node.
        return registration.validate_node(self._node)


async def verify() -> None:
    registry = NodeRegistry()
    registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT)
    registry.register_llm(TypedLLMNode, LEAF_CONTRACT)
    registration = registry.get(NodeId("typed-python"), LEAF_CONTRACT)
    assert_type(registration, NodeRegistration[NodeInput, LeafOutput, Never])
    view: DAGReadView = FakeReadView(LeafOutput(value=3))
    executor: PythonExecutor = FakeExecutor()
    node = TypedPythonNode(request_value=5, phase=ExecutionPhase.POST_LLM)
    assert_type(node.phase, PythonExecutionPhase)
    assert_type(await node.prepare_input(view), NodeInput)
    assert_type(view.require(REQUIRED_LEAF), LeafOutput)
    assert_type(view.optional(OPTIONAL_COMPOSITE), CompositeOutput | None)
    assert_type(await executor.execute(node, NodeInput(value=3)), LeafOutput)
    assert_type(await node.execute(NodeInput(value=3)), LeafOutput)
    factory: ExecutionBindings = Factory(node)
    assert_type(factory.make_node(registration), BaseNode[NodeInput, LeafOutput, Never])
    response: ResponseBinding[LeafOutput] = Response()
    assert_type(response.resolve(view), ResolveResult[LeafOutput])
    transition: TransitionBinding = Transition()
    assert_type(transition.transition(view), TaskType | None)
    extension: SnapshotExtension[LeafOutput] = Extension()
    assert_type(extension.capture(), LeafOutput)
    lifecycle: OutputLifecycle[LeafOutput] = Extension()
    await lifecycle.validate_restored(LeafOutput(value=1))
    compiled = CompiledNode[NodeInput, LeafOutput, Never](node, ())
    assert_type(compiled.node, BaseNode[NodeInput, LeafOutput, Never])
    python_class = register_python(FakeExecutor, LEAF_CONTRACT, registry=NodeRegistry())(TypedPythonNode)
    assert_type(python_class, type[PythonNode[NodeInput, LeafOutput, Never]])
    register_llm(LEAF_CONTRACT, registry=NodeRegistry())(TypedLLMNode)


def verify_plan_lookup(plan: ExecutionPlan) -> None:
    assert_type(plan.get(NodeId("typed-python"), LEAF_CONTRACT), CompiledNode[NodeInput, LeafOutput, Never])


def verify_validation() -> None:
    structural = ContractValidator()
    semantic = NodeValidator()
    llm = LLMValidator(structural, semantic)
    assert_type(structural.validate(LeafOutput(value=1), LeafOutput), tuple[LeafOutput | None, ValidationResult])
    assert_type(structural.parse_json('{"leaves":[]}', CompositeOutput), tuple[CompositeOutput | None, ValidationResult])
    ctx = NodeValidationContext(LeafOutput(value=1), identity())
    assert_type(ctx.output, LeafOutput)
    assert_type(semantic.validate(ctx, LEAF_CONTRACT), ValidationResult)
    assert_type(llm.validate('{"value":1}', LEAF_CONTRACT, identity()), tuple[LeafOutput | None, ValidationResult])
    callback = RecordingValidator[LeafOutput](ValidationResult(status=ValidationStatus.OK))
    contract = NodeContract[NodeInput, LeafOutput, Never](
        NodeInput, LeafOutput, ContractId("test.validated"), ContractVersion("1"), (), validator=callback,
        error_types=(),
    )
    assert_type(semantic.validate(ctx, contract), ValidationResult)


def verify_catalog(
    catalog: DAGContext, required: RequiredOutput[LeafOutput],
    optional: OptionalOutput[CompositeOutput], record: OutputRecord[LeafOutput],
) -> None:
    view = catalog.read_view(NodeId("consumer"))
    assert_type(view, PublishedDAGReadView)
    port: DAGReadView = view
    assert_type(view.require(required), LeafOutput)
    assert_type(view.optional(optional), CompositeOutput | None)
    assert_type(port.require(required), LeafOutput)
    assert_type(view.dependency_reads, tuple[DependencyRead, ...])
    assert_type(view.domain_reads, tuple[DomainReadEvidence, ...])
    assert_type(catalog.current_outputs, tuple[ExecutionIdentity, ...])
    assert_type(catalog.publish(record), None)

    assert_type(catalog.invalidate_for_reuse({}), tuple[ExecutionIdentity, ...])


async def verify_runner(
    node: TypedPythonNode, view: PublishedDAGReadView, registration: NodeRegistration[NodeInput, LeafOutput, Never],
) -> None:
    executor: PythonExecutor = PythonNodeExecutor()
    assert_type(await executor.execute(node, NodeInput(value=1)), LeafOutput)
    runner = NodeRunner(ContractValidator(), NodeValidator())
    outcome = await runner.run(node, view, identity(), registration, executor)
    assert_type(outcome, NodeOutcome[LeafOutput, Never])
    assert_type(outcome.output, LeafOutput | None)
    assert_type(outcome.reads, tuple[DependencyRead, ...])
    assert_type(view.execution_id, ExecutionId)


async def verify_typed_errors(view: PublishedDAGReadView, catalog: DAGContext) -> None:
    registry = NodeRegistry()
    registry.register_python(TypedErrorNode, PythonNodeExecutor, ERROR_CONTRACT)
    registration = registry.get(NodeId("typed-error"), ERROR_CONTRACT)
    assert_type(registration, NodeRegistration[NodeInput, LeafOutput, TestNodeError | TestOtherError])
    assert_type(GraphBindings().make_node(registration), BaseNode[NodeInput, LeafOutput, TestNodeError | TestOtherError])
    runner = NodeRunner(ContractValidator(), NodeValidator())
    outcome = await runner.run(TypedErrorNode(), view, identity(), registration, PythonNodeExecutor())
    assert_type(outcome, NodeOutcome[LeafOutput, TestNodeError | TestOtherError])
    assert_type(outcome.error, TestNodeError | TestOtherError | None)
    assert_type(catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT), TestNodeError | TestOtherError | None)
    assert_type(catalog.close_error(identity(), TestNodeError(item_id=1), ERROR_CONTRACT), None)
    assert_type(PythonNodeError(TestNodeError(item_id=1)).error, TestNodeError)


async def verify_coordinator(plan: ExecutionPlan, state: ExecutionState) -> None:
    executor = DAGExecutor(NodeRunner(ContractValidator(), NodeValidator()), {PythonNodeExecutor: PythonNodeExecutor()})
    assert_type(await executor.run_python_phase(plan, state, ExecutionPhase.PRE_LLM, PlanRevision("plan-1")), LevelDecision)
    assert_type(state.traces, tuple[ExecutionTrace, ...])
    assert_type(state.levels, tuple[ExecutionLevelSnapshot, ...])
    assert_type(state.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT), TestNodeError | TestOtherError | None)


def verify_diagnostics(view: PublishedDAGReadView) -> None:
    assert_type(view.requirements, tuple[OutputRequirement, ...])
    assert_type(CancellationRequest().source, CancellationSource)
    event = ReplanDiagnostic(
        identity=identity(), pass_number=0, phase=ExecutionPhase.PRE_LLM, level=0, timestamp=1.0,
        code=ExecutionEventCode.REPLAN_REQUESTED, severity=ExecutionSeverity.INFO, status=NodeStatus.GATED,
        message="gate", next_task_type=TaskType.SCENE_INIT,
    )
    assert_type(event.next_task_type, TaskType)
    assert_type(emit(event), None)


def verify_snapshot(state: ExecutionState) -> None:
    service = ExecutionSnapshotService[LeafOutput](Extension())
    snapshot = service.capture(state)
    assert_type(snapshot, SessionSnapshot[LeafOutput])
    assert_type(snapshot.extension, LeafOutput | None)
    assert_type(snapshot.catalog.record(NodeId("typed-python"), LEAF_CONTRACT), OutputRecord[LeafOutput] | None)
    assert_type(snapshot.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT), TestNodeError | TestOtherError | None)
    store = SnapshotStore[LeafOutput]()
    assert_type(store.save(snapshot), None)
    assert_type(store.load(state.catalog.execution_id), SessionSnapshot[LeafOutput] | None)
    assert_type(ExecutionSnapshotService[Never]().capture(state), SessionSnapshot[Never])


async def verify_restore(snapshot: SessionSnapshot[LeafOutput], registry: NodeRegistry) -> None:
    service = ExecutionSnapshotService[LeafOutput](Extension())
    state = await service.restore(snapshot, registry)
    assert_type(state, ExecutionState)
    assert_type(service.capture(state), SessionSnapshot[LeafOutput])
    assert_type(state.release(), None)
    assert_type(state.is_released, bool)


def verify_payload(
    builder: LLMGroupPayloadBuilder,
    node: LLMNode[NodeInput, LeafOutput, Never],
    registration: NodeRegistration[NodeInput, LeafOutput, Never],
    other: NodeSection[OtherInput],
) -> None:
    section = builder.section(node, registration, NodeInput(value=1), language="ru")
    assert_type(section, NodeSection[NodeInput])
    assert_type(section.input, NodeInput)
    payload = builder.build((section, other), player_message="message", language="ru")
    assert_type(payload, LLMPayload)
    assert_type(payload.sections, tuple[NodeSection[BaseModel], ...])
    assert_type(payload.to_dict(), dict[str, object])
    assert_type(payload.response_format_schema, dict[str, object])


def verify_repair(
    projector: DSLFailureProjector, builder: RepairBuilder, base: LLMPayload,
    node: LLMNode[NodeInput, LeafOutput, Never], registration: NodeRegistration[NodeInput, LeafOutput, Never],
    validation: ValidationResult, other: NodeFailureContext[CompositeOutput],
) -> None:
    failure = projector.project(node, registration, identity(), validation, raw_output="{}")
    assert_type(failure, NodeFailureContext[LeafOutput])
    assert_type(failure.output_type, type[LeafOutput])
    assert_type(failure.validation, ValidationResult)
    payload = builder.build(base, (failure, other))
    assert_type(payload, LLMRepairPayload)
    assert_type(payload.errors, tuple[NodeFailureContext[BaseModel], ...])
    assert_type(payload.to_dict(), dict[str, object])


async def verify_llm_execution(
    executor: DAGExecutor, aggregate: LLMAggregateExecutor, request: LLMRequest,
    plan: ExecutionPlan, group: LLMGroup, state: ExecutionState, options: LLMExecutionOptions,
    views: dict[NodeId, PublishedDAGReadView], record: OutputRecord[LeafOutput],
) -> None:
    assert_type(await executor.run_llm_phase(plan, state, PlanRevision("r1"), aggregate, request, options=options), LevelDecision)
    assert_type(await aggregate.execute(plan, group, (identity(),), views, request, options=options), tuple[NodeOutcome[BaseModel, NodeError], ...])
    assert_type(state.catalog.publish_batch((record,)), None)
    assert_type(state.levels[0].phase, ExecutionPhase)


async def verify_engine(
    engine: LLMExecutionEngine[LeafOutput, CompositeOutput], options: LLMExecutionOptions,
    hooks: LifecycleBinding[LeafOutput], view: DAGReadView, state: ExecutionState,
) -> None:
    assert_type(await engine.run(ExecutionId("e1"), TaskType.SCENE_INIT, max_passes=3, options=options), ResolveResult[LeafOutput])
    assert_type(await engine.resume(ExecutionId("e1"), max_passes=3, options=options), ResolveResult[LeafOutput])
    assert_type(ResponseResolver(LeafOutput).resolve(hooks, view), ResolveResult[LeafOutput])
    assert_type(state.set_cursor(ExecutionCursor(TaskType.SCENE_INIT, PassStage.LLM)), None)
    assert_type(state.cursor, ExecutionCursor | None)
