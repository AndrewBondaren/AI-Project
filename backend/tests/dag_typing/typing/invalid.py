"""Every marked line must produce exactly the declared Pyright error."""

from pydantic import BaseModel

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.executionBindings import ResponseBinding, SnapshotExtension
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.nodeTypes.compiledNode import CompiledNode
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase
from tests.dag_typing.fixtures import (
    CompositeOutput, FakeExecutor, LEAF_CONTRACT, LeafOutput, NodeInput,
    OPTIONAL_COMPOSITE, OtherInput, REQUIRED_LEAF, TypedPythonNode,
)


async def wrong_calls(view: DAGReadView, executor: PythonExecutor, node: TypedPythonNode) -> None:
    await executor.execute(node, OtherInput(text="wrong"))  # expect: reportArgumentType
    await node.execute(OtherInput(text="wrong"))  # expect: reportArgumentType
    result: CompositeOutput = await executor.execute(node, NodeInput(value=1))  # expect: reportAssignmentType
    required: CompositeOutput = view.require(REQUIRED_LEAF)  # expect: reportAssignmentType
    optional: LeafOutput | None = view.optional(OPTIONAL_COMPOSITE)  # expect: reportAssignmentType
    nonoptional: CompositeOutput = view.optional(OPTIONAL_COMPOSITE)  # expect: reportAssignmentType
    print(result, required, optional, nonoptional)


class BadNode(PythonNode[NodeInput, LeafOutput]):
    async def prepare_input(self, view: DAGReadView) -> OtherInput:  # expect: reportIncompatibleMethodOverride
        return OtherInput(text="wrong")

    async def execute(self, input: NodeInput) -> CompositeOutput:  # expect: reportIncompatibleMethodOverride
        return CompositeOutput(leaves=())


def wrong_bindings(response: ResponseBinding[LeafOutput], extension: SnapshotExtension[LeafOutput]) -> None:
    registry = NodeRegistry()
    wrong_input = NodeContract(OtherInput, LeafOutput, ContractId("wrong.input"), ContractVersion("1"), ())
    wrong_output = NodeContract(NodeInput, CompositeOutput, ContractId("wrong.output"), ContractVersion("1"), ())
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
    wrong: CompiledNode[OtherInput, LeafOutput] = plan.get(NodeId("typed-python"), LEAF_CONTRACT)  # expect: reportAssignmentType
    print(wrong)
