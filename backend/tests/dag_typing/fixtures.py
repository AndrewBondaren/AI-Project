"""Small immutable test contracts; never production node schemas."""

from typing import Never
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.nodeTypes.pythonNode import PythonNode
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.taskType import TaskType
from app.application.engine.runtime.validation.nodeValidationContext import NodeValidationContext
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.engine.validation.validationStatus import ValidationResult

from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, DomainRevision, ExecutionId, ExecutionIdentity, NodeId, PlanRevision,
)


class LeafOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: int


class CompositeOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
    leaves: tuple[LeafOutput, ...]


class LeafTupleOutput(RootModel[tuple[LeafOutput, ...]]):
    model_config = ConfigDict(frozen=True, strict=True)


class BoundedOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    value: int = Field(default=5, ge=0)


class MutableBoundaryOutput(BaseModel):
    value: int


class FrozenListOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    leaves: list[LeafOutput]


class AlwaysLeafOutput(LeafOutput):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")


class AlwaysCompositeOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
    leaves: tuple[AlwaysLeafOutput, ...]


class NormalizedOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class RecordingValidator[O: BaseModel]:
    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        self.contexts: list[NodeValidationContext[O]] = []

    def __call__(self, ctx: NodeValidationContext[O]) -> ValidationResult:
        self.contexts.append(ctx)
        return self.result


class NodeInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: int


class OtherInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str


class TestNodeError(NodeError):
    item_id: int = Field(ge=0)


class TestOtherError(NodeError):
    description: str


@dataclass(frozen=True, kw_only=True)
class TypedErrorNode(PythonNode[NodeInput, LeafOutput, TestNodeError | TestOtherError]):
    id: NodeId = NodeId("typed-error")
    failure: TestNodeError | TestOtherError | None = None

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        return NodeInput(value=1)

    async def execute(self, input: NodeInput) -> LeafOutput:
        if self.failure is not None:
            raise PythonNodeError(self.failure)
        return LeafOutput(value=input.value)


ERROR_CONTRACT = NodeContract[NodeInput, LeafOutput, TestNodeError | TestOtherError](
    NodeInput, LeafOutput, ContractId("test.errors"), ContractVersion("1"), (),
    error_types=(TestNodeError, TestOtherError),
)


REQUIRED_LEAF = RequiredOutput(OutputRef(NodeId("producer"), LeafOutput))
OPTIONAL_COMPOSITE = OptionalOutput(OutputRef(NodeId("optional-producer"), CompositeOutput))
OPTIONAL_LEAF = OptionalOutput(OutputRef(NodeId("producer"), LeafOutput))
LEAF_CONTRACT = NodeContract[NodeInput, LeafOutput, Never](
    NodeInput, LeafOutput, ContractId("test.leaf"), ContractVersion("1"),
    reads=(REQUIRED_LEAF, OPTIONAL_COMPOSITE),
    error_types=(),
)


@dataclass(frozen=True, kw_only=True)
class TypedPythonNode(PythonNode[NodeInput, LeafOutput, Never]):
    id: NodeId = NodeId("typed-python")
    deps: tuple[NodeId, ...] = (NodeId("producer"), NodeId("optional-producer"))
    request_value: int

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        return NodeInput(value=view.require(REQUIRED_LEAF).value + self.request_value)

    async def execute(self, input: NodeInput) -> LeafOutput:
        return LeafOutput(value=input.value)


@dataclass(frozen=True, kw_only=True)
class TypedLLMNode(LLMNode[NodeInput, LeafOutput, Never]):
    id: NodeId = NodeId("typed-llm")

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        return NodeInput(value=1)


class FakeReadView:
    """Test port implementation; never substitutes for catalog runtime tests."""

    def __init__(self, output: BaseModel | None = None) -> None:
        self.output = output

    def require[O: BaseModel](self, req: RequiredOutput[O]) -> O:
        output = self.optional(OptionalOutput(req.ref))
        if output is None:
            raise LookupError(req.ref.producer)
        return output

    def optional[O: BaseModel](self, req: OptionalOutput[O]) -> O | None:
        if self.output is None:
            return None
        if not isinstance(self.output, req.ref.output_type):
            raise TypeError("wrong test output")
        return self.output

    def record_domain_read(self, domain: str, revision: DomainRevision | None) -> None:
        pass


class FakeExecutor:
    async def execute[I: BaseModel, O: BaseModel, E: NodeError](self, node: PythonNode[I, O, E], input: I) -> O:
        return await node.execute(input)


class GraphRuleState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    task_type: TaskType = TaskType.SCENE_NARRATION


class DerivedLeafOutput(LeafOutput):
    pass


class GraphBindings:
    def __init__(self) -> None:
        self.nodes: dict[NodeId, object] = {}

    def make_node[I: BaseModel, O: BaseModel, E: NodeError](
        self, registration: NodeRegistration[I, O, E],
    ) -> BaseNode[I, O, E]:
        return registration.validate_node(self.nodes[registration.node_id])


class GraphPythonNode[I: BaseModel, O: BaseModel, E: NodeError](PythonNode[I, O, E]):
    async def prepare_input(self, view: DAGReadView) -> I:
        raise AssertionError("compiler must not prepare Input")

    async def execute(self, input: I) -> O:
        raise AssertionError("compiler must not execute nodes")


class GraphProducer(GraphPythonNode[NodeInput, LeafOutput, Never]):
    id = NodeId("producer")


class GraphConsumer(GraphPythonNode[NodeInput, LeafOutput, Never]):
    id = NodeId("consumer")


class GraphPeer(GraphPythonNode[NodeInput, LeafOutput, Never]):
    id = NodeId("peer")


class GraphDerivedProducer(GraphPythonNode[NodeInput, DerivedLeafOutput, Never]):
    id = NodeId("derived-producer")


class GraphLLMNode(LLMNode[NodeInput, LeafOutput, Never]):
    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        raise AssertionError("compiler must not prepare LLM Input")


class GraphLLMProducer(GraphLLMNode):
    id = NodeId("llm-producer")


class GraphLLMConsumer(GraphLLMNode):
    id = NodeId("llm-consumer")


class GraphOptionalConsumer(PythonNode[CompositeOutput, LeafOutput, Never]):
    id = NodeId("optional-consumer")

    async def prepare_input(self, view: DAGReadView) -> CompositeOutput:
        value = view.optional(OPTIONAL_LEAF)
        return CompositeOutput(leaves=() if value is None else (value,))

    async def execute(self, input: CompositeOutput) -> LeafOutput:
        raise AssertionError("graph preparation test must not execute node")


def identity(node: str = "producer", attempt: int = 1) -> ExecutionIdentity:
    return ExecutionIdentity(
        execution_id=ExecutionId("execution-1"), node_id=NodeId(node),
        attempt=attempt, plan_revision=PlanRevision("plan-1"),
    )
