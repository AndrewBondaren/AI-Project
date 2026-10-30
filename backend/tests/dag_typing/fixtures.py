"""Small immutable test contracts; never production node schemas."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.outputRef import OptionalOutput, OutputRef, RequiredOutput
from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.nodeTypes.pythonNode import PythonNode

from app.dataModel.engine.dag.identity import (
    ContractId, ContractVersion, DomainRevision, ExecutionId, ExecutionIdentity, NodeId, PlanRevision,
)


class LeafOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: int


class CompositeOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
    leaves: tuple[LeafOutput, ...]


class NodeInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: int


class OtherInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str


REQUIRED_LEAF = RequiredOutput(OutputRef(NodeId("producer"), LeafOutput))
OPTIONAL_COMPOSITE = OptionalOutput(OutputRef(NodeId("optional-producer"), CompositeOutput))
LEAF_CONTRACT = NodeContract(
    NodeInput, LeafOutput, ContractId("test.leaf"), ContractVersion("1"),
    reads=(REQUIRED_LEAF, OPTIONAL_COMPOSITE),
)


@dataclass(frozen=True, kw_only=True)
class TypedPythonNode(PythonNode[NodeInput, LeafOutput]):
    id: NodeId = NodeId("typed-python")
    deps: tuple[NodeId, ...] = (NodeId("producer"), NodeId("optional-producer"))
    request_value: int

    async def prepare_input(self, view: DAGReadView) -> NodeInput:
        return NodeInput(value=view.require(REQUIRED_LEAF).value + self.request_value)

    async def execute(self, input: NodeInput) -> LeafOutput:
        return LeafOutput(value=input.value)


@dataclass(frozen=True, kw_only=True)
class TypedLLMNode(LLMNode[NodeInput, LeafOutput]):
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
    async def execute[I: BaseModel, O: BaseModel](self, node: PythonNode[I, O], input: I) -> O:
        return await node.execute(input)


def identity(node: str = "producer", attempt: int = 1) -> ExecutionIdentity:
    return ExecutionIdentity(
        execution_id=ExecutionId("execution-1"), node_id=NodeId(node),
        attempt=attempt, plan_revision=PlanRevision("plan-1"),
    )
