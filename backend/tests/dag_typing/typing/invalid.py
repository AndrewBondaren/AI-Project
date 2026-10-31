"""Every marked line must produce exactly the declared Pyright error."""

from typing import Never
from pydantic import BaseModel

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.diagnostics.dagLog import emit
from app.application.engine.diagnostics.events import ReplanDiagnostic
from app.application.engine.contracts.executionBindings import ResponseBinding, SnapshotExtension
from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.runtime.prompt.pojo.nodeSection import NodeSection
from app.application.engine.runtime.prompt.pojo.llmPayload import LLMPayload
from app.application.engine.runtime.repair.repairBuilder import RepairBuilder
from app.application.engine.runtime.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.llm.models import ChatMessage
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.dataModel.engine.dag.records import OutputRecord
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.nodeTypes.compiledNode import CompiledNode
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.context.dagContext import DAGContext
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, NodeOutcome
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.diagnostics import CancellationRequest, ExecutionEventCode, ExecutionSeverity
from app.application.engine.runtime.execution.nodeRunner import NodeRunner
from app.application.engine.runtime.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.runtime.validation.nodeValidator import NodeValidator
from app.application.engine.validation.validationStatus import ValidationResult, ValidationStatus
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId, PlanRevision
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase
from tests.dag_typing.fixtures import (
    CompositeOutput, FakeExecutor, LEAF_CONTRACT, LeafOutput, NodeInput,
    OPTIONAL_COMPOSITE, OtherInput, REQUIRED_LEAF, TypedPythonNode,
    RecordingValidator, identity,
    ERROR_CONTRACT, TestNodeError, TestOtherError, TypedErrorNode,
)


async def wrong_calls(view: DAGReadView, executor: PythonExecutor, node: TypedPythonNode) -> None:
    await executor.execute(node, OtherInput(text="wrong"))  # expect: reportArgumentType
    await node.execute(OtherInput(text="wrong"))  # expect: reportArgumentType
    result: CompositeOutput = await executor.execute(node, NodeInput(value=1))  # expect: reportAssignmentType
    required: CompositeOutput = view.require(REQUIRED_LEAF)  # expect: reportAssignmentType
    optional: LeafOutput | None = view.optional(OPTIONAL_COMPOSITE)  # expect: reportAssignmentType
    nonoptional: CompositeOutput = view.optional(OPTIONAL_COMPOSITE)  # expect: reportAssignmentType
    print(result, required, optional, nonoptional)


class BadNode(PythonNode[NodeInput, LeafOutput, Never]):
    async def prepare_input(self, view: DAGReadView) -> OtherInput:  # expect: reportIncompatibleMethodOverride
        return OtherInput(text="wrong")

    async def execute(self, input: NodeInput) -> CompositeOutput:  # expect: reportIncompatibleMethodOverride
        return CompositeOutput(leaves=())


def wrong_bindings(response: ResponseBinding[LeafOutput], extension: SnapshotExtension[LeafOutput]) -> None:
    registry = NodeRegistry()
    wrong_input = NodeContract[OtherInput, LeafOutput, Never](OtherInput, LeafOutput, ContractId("wrong.input"), ContractVersion("1"), (), error_types=())
    wrong_output = NodeContract[NodeInput, CompositeOutput, Never](NodeInput, CompositeOutput, ContractId("wrong.output"), ContractVersion("1"), (), error_types=())
    registry.register_python(TypedPythonNode, FakeExecutor, wrong_input)  # expect: reportArgumentType
    registry.register_python(TypedPythonNode, FakeExecutor, wrong_output)  # expect: reportArgumentType
    registry.register_python(TypedPythonNode, FakeExecutor)  # expect: reportCallIssue
    other_response: ResponseBinding[CompositeOutput] = response  # expect: reportAssignmentType
    other_extension: SnapshotExtension[BaseModel] = extension  # expect: reportAssignmentType
    print(other_response, other_extension, LEAF_CONTRACT)


def wrong_phases() -> None:
    TypedPythonNode(request_value=1, phase="pre_llm")  # expect: reportArgumentType
    TypedPythonNode(request_value=1, phase=ExecutionPhase.LLM)  # expect: reportArgumentType
    phase: PythonExecutionPhase = ExecutionPhase.LLM  # expect: reportAssignmentType
    print(phase)


def wrong_plan_lookup(plan: ExecutionPlan) -> None:
    wrong: CompiledNode[OtherInput, LeafOutput, Never] = plan.get(NodeId("typed-python"), LEAF_CONTRACT)  # expect: reportAssignmentType
    print(wrong)


async def wrong_coordinator(executor: DAGExecutor, plan: ExecutionPlan, state: ExecutionState) -> None:
    await executor.run_python_phase(plan, state, ExecutionPhase.LLM, PlanRevision("plan-1"))  # expect: reportArgumentType
    await executor.run_python_phase(plan, state, "pre_llm", PlanRevision("plan-1"))  # expect: reportArgumentType
    wrong: tuple[NodeOutcome[LeafOutput, TestNodeError], ...] = state.traces  # expect: reportAssignmentType
    payload: LeafOutput = state.traces[0]  # expect: reportAssignmentType
    print(wrong, payload)


def wrong_diagnostics() -> None:
    CancellationRequest(source="user")  # expect: reportArgumentType
    CancellationRequest(reason="requested")  # expect: reportArgumentType
    emit(LeafOutput(value=1))  # expect: reportArgumentType
    ReplanDiagnostic(identity=identity(), pass_number=0, phase=ExecutionPhase.PRE_LLM, level=0, timestamp=1.0, code=ExecutionEventCode.REPLAN_REQUESTED, severity=ExecutionSeverity.INFO, status=NodeStatus.GATED, message="gate", next_task_type="scene_init")  # expect: reportArgumentType


def wrong_snapshot(
    leaf: SessionSnapshot[LeafOutput], composite: SessionSnapshot[CompositeOutput],
    extension: SnapshotExtension[CompositeOutput],
) -> None:
    wrong: SessionSnapshot[CompositeOutput] = leaf  # expect: reportAssignmentType
    wrong_record: OutputRecord[CompositeOutput] | None = leaf.catalog.record(NodeId("typed-python"), LEAF_CONTRACT)  # expect: reportAssignmentType
    wrong_error: TestNodeError | None = leaf.catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT)  # expect: reportAssignmentType
    ExecutionSnapshotService[LeafOutput](extension)  # expect: reportArgumentType
    SnapshotStore[LeafOutput]().save(composite)  # expect: reportArgumentType
    SnapshotStore[LeafOutput]().load("execution-1")  # expect: reportArgumentType
    print(wrong, wrong_record, wrong_error)


async def wrong_error_contracts(view: PublishedDAGReadView, catalog: DAGContext, runner: NodeRunner) -> None:
    registry = NodeRegistry()
    registry.register_python(TypedErrorNode, PythonNodeExecutor, ERROR_CONTRACT)
    registration = registry.get(NodeId("typed-error"), ERROR_CONTRACT)
    wrong: NodeOutcome[LeafOutput, TestOtherError] = await runner.run(TypedErrorNode(), view, identity(), registration, PythonNodeExecutor())  # expect: reportAssignmentType
    wrong_error: TestNodeError | None = catalog.node_error(NodeId("typed-error"), ERROR_CONTRACT)  # expect: reportAssignmentType
    catalog.close_error(identity(), LeafOutput(value=1), ERROR_CONTRACT)  # expect: reportArgumentType
    NodeOutcome[LeafOutput, TestNodeError](identity=identity(), status=NodeStatus.FAILED, started_at=1.0, completed_at=2.0, error=TestOtherError(description="wrong"))  # expect: reportArgumentType
    PythonNodeError[LeafOutput](LeafOutput(value=1))  # expect: reportInvalidTypeArguments
    registry.register_python(TypedPythonNode, FakeExecutor, ERROR_CONTRACT)  # expect: reportArgumentType
    NodeContract[NodeInput, LeafOutput, TestNodeError](NodeInput, LeafOutput, ContractId("wrong.errors"), ContractVersion("1"), (), error_types=(TestOtherError,))  # expect: reportArgumentType
    NodeContract[NodeInput, LeafOutput, TestNodeError](NodeInput, LeafOutput, ContractId("wrong.policy"), ContractVersion("1"), (), error_types=(TestNodeError,), error_policy=wrong_error_policy)  # expect: reportArgumentType
    print(wrong, wrong_error)


def wrong_error_policy(error: TestOtherError) -> GateSignal | None:
    return None


async def wrong_restore(snapshot: SessionSnapshot[CompositeOutput], registry: NodeRegistry) -> None:
    await ExecutionSnapshotService[LeafOutput]().restore(snapshot, registry)  # expect: reportArgumentType
    await ExecutionSnapshotService[LeafOutput]().restore(LeafOutput(value=1), registry)  # expect: reportArgumentType


def wrong_payload(
    builder: LLMGroupPayloadBuilder, node: LLMNode[NodeInput, LeafOutput, Never],
    registration: NodeRegistration[NodeInput, LeafOutput, Never],
) -> None:
    builder.section(
        node,  # expect: reportArgumentType
        registration,  # expect: reportArgumentType
        OtherInput(text="wrong"), language="ru",
    )
    builder.section(node, registration, {"value": 1}, language="ru")  # expect: reportArgumentType
    section = builder.section(node, registration, NodeInput(value=1), language="ru")
    wrong: NodeSection[OtherInput] = section  # expect: reportAssignmentType
    builder.build((NodeInput(value=1),), player_message="", language="ru")  # expect: reportArgumentType
    print(wrong)


def wrong_repair(
    projector: DSLFailureProjector, builder: RepairBuilder, base: LLMPayload,
    node: LLMNode[NodeInput, LeafOutput, Never], registration: NodeRegistration[NodeInput, LeafOutput, Never],
    validation: ValidationResult,
) -> None:
    failure = projector.project(node, registration, identity(), validation, raw_output="{}")
    wrong: NodeFailureContext[CompositeOutput] = failure  # expect: reportAssignmentType
    projector.project(node, registration, identity(), validation, raw_output={})  # expect: reportArgumentType
    builder.build(base, (failure,), mode="economy")  # expect: reportArgumentType
    builder.build(base, (validation,))  # expect: reportArgumentType
    print(wrong)


async def bad_llm_request(messages: list[ChatMessage], schema: dict[str, object], *, enable_thinking: bool, temperature: float) -> LeafOutput:
    return LeafOutput(value=1)


async def wrong_llm_execution(
    executor: DAGExecutor, aggregate: LLMAggregateExecutor, plan: ExecutionPlan, state: ExecutionState,
    request: LLMRequest, options: LLMExecutionOptions,
) -> None:
    await executor.run_llm_phase(plan, state, PlanRevision("r1"), aggregate, bad_llm_request, options=options)  # expect: reportArgumentType
    await executor.run_llm_phase(plan, state, PlanRevision("r1"), aggregate, request, options={})  # expect: reportArgumentType
    state.catalog.publish_batch((LeafOutput(value=1),))  # expect: reportArgumentType
    LLMExecutionOptions(player_message="", language="ru", repair_iterations=1, repair_mode="maximum")  # expect: reportArgumentType


def wrong_validation() -> None:
    wrong: tuple[CompositeOutput | None, ValidationResult] = ContractValidator().validate(LeafOutput(value=1), LeafOutput)  # expect: reportAssignmentType
    wrong_callback = RecordingValidator[CompositeOutput](ValidationResult(status=ValidationStatus.OK))
    contract = NodeContract[NodeInput, LeafOutput, Never](NodeInput, LeafOutput, ContractId("test"), ContractVersion("1"), (), validator=wrong_callback, error_types=())  # expect: reportArgumentType
    wrong_ctx = NodeValidationContext(CompositeOutput(leaves=()), identity())
    NodeValidator().validate(wrong_ctx, LEAF_CONTRACT)  # expect: reportArgumentType
    print(wrong, contract)


def wrong_catalog_reads(view: PublishedDAGReadView, catalog: DAGContext) -> None:
    wrong: CompositeOutput = view.require(REQUIRED_LEAF)  # expect: reportAssignmentType
    optional: LeafOutput | None = view.optional(OPTIONAL_COMPOSITE)  # expect: reportAssignmentType
    catalog.publish(LeafOutput(value=1))  # expect: reportArgumentType
    print(wrong, optional)


async def wrong_runner(
    node: TypedPythonNode, view: PublishedDAGReadView, runner: NodeRunner,
    registration: NodeRegistration[NodeInput, LeafOutput, Never], wrong_registration: NodeRegistration[OtherInput, LeafOutput, Never],
) -> None:
    executor = PythonNodeExecutor()
    await executor.execute(node, OtherInput(text="wrong"))  # expect: reportArgumentType
    wrong: NodeOutcome[CompositeOutput, Never] = await runner.run(node, view, identity(), registration, executor)  # expect: reportAssignmentType
    await runner.run(node, view, identity(), wrong_registration, executor)  # expect: reportArgumentType
    print(wrong)
