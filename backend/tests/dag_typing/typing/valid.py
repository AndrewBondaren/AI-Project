"""Positive static API probes, including request-local factories and ports."""

from typing import assert_type

from pydantic import BaseModel

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.executionBindings import (
    ExecutionBindings, ResolveResult, ResponseBinding, SnapshotExtension, TransitionBinding,
)
from app.application.engine.contracts.nodeContract import OutputLifecycle
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.nodeTypes.compiledNode import CompiledNode
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.registration.nodeRegistry import NodeRegistry, register_llm, register_python
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId
from app.dataModel.engine.dag.executionPhase import ExecutionPhase, PythonExecutionPhase
from tests.dag_typing.fixtures import (
    CompositeOutput, FakeExecutor, FakeReadView, LEAF_CONTRACT, LeafOutput, NodeInput,
    OPTIONAL_COMPOSITE, REQUIRED_LEAF, TypedLLMNode, TypedPythonNode,
)


class Response:
    def resolve(self, view: DAGReadView) -> ResolveResult[LeafOutput]:
        return ResolveResult(ok=True, data=view.require(REQUIRED_LEAF))


class Transition:
    def transition(self, view: DAGReadView) -> TaskType | None:
        return None


class Extension:
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

    def make_node[I: BaseModel, O: BaseModel](
        self, registration: NodeRegistration[I, O],
    ) -> BaseNode[I, O]:
        # The fake integration supplies a request-local, already constructed node.
        return registration.validate_node(self._node)


async def verify() -> None:
    registry = NodeRegistry()
    registry.register_python(TypedPythonNode, FakeExecutor, LEAF_CONTRACT)
    registry.register_llm(TypedLLMNode, LEAF_CONTRACT)
    registration = registry.get(NodeId("typed-python"), LEAF_CONTRACT)
    assert_type(registration, NodeRegistration[NodeInput, LeafOutput])
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
    assert_type(factory.make_node(registration), BaseNode[NodeInput, LeafOutput])
    response: ResponseBinding[LeafOutput] = Response()
    assert_type(response.resolve(view), ResolveResult[LeafOutput])
    transition: TransitionBinding = Transition()
    assert_type(transition.transition(view), TaskType | None)
    extension: SnapshotExtension[LeafOutput] = Extension()
    assert_type(extension.capture(), LeafOutput)
    lifecycle: OutputLifecycle[LeafOutput] = Extension()
    await lifecycle.validate_restored(LeafOutput(value=1))
    compiled = CompiledNode[NodeInput, LeafOutput](node, ())
    assert_type(compiled.node, BaseNode[NodeInput, LeafOutput])
    python_class = register_python(FakeExecutor, LEAF_CONTRACT, registry=NodeRegistry())(TypedPythonNode)
    assert_type(python_class, type[PythonNode[NodeInput, LeafOutput]])
    register_llm(LEAF_CONTRACT, registry=NodeRegistry())(TypedLLMNode)
