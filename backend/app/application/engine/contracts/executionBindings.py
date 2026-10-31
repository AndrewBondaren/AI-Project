"""Integration ports; concrete requests, effects and policy belong to GEN."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from app.dataModel.engine.dag.identity import NodeId, PlanRevision
from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.dataModel.engine.dag.executionPhase import ExecutionPhase

if TYPE_CHECKING:
    from app.application.engine.runtime.dag.executionPlan import ExecutionPlan

O = TypeVar("O", bound=BaseModel, covariant=True)
S = TypeVar("S", bound=BaseModel)


@dataclass(frozen=True)
class ResolveResult(Generic[O]):
    ok: bool
    data: O | None = None
    error: str | None = None


class ResponseBinding(Protocol[O]):
    def resolve(self, view: DAGReadView) -> ResolveResult[O]: ...


class TransitionBinding(Protocol):
    def transition(self, view: DAGReadView) -> TaskType | None: ...


class PassStage(StrEnum):
    PRE_LLM = ExecutionPhase.PRE_LLM.value
    LLM = ExecutionPhase.LLM.value
    POST_LLM = ExecutionPhase.POST_LLM.value
    TRANSITION = "transition"
    EFFECTS = "effects"
    RESPONSE = "response"


@dataclass(frozen=True)
class ExecutionCursor:
    task_type: TaskType
    stage: PassStage

    def __post_init__(self) -> None:
        TypeAdapter(TaskType).validate_python(self.task_type, strict=True)
        TypeAdapter(PassStage).validate_python(self.stage, strict=True)


class LifecycleBinding(ResponseBinding[O], TransitionBinding, Protocol[O]):
    @property
    def consumer(self) -> NodeId: ...

    @property
    def reads(self) -> tuple[RequiredOutput[BaseModel] | OptionalOutput[BaseModel], ...]: ...

    @property
    def response_type(self) -> type[O]: ...

    def compile(self, task_type: TaskType, pass_number: int) -> tuple[PlanRevision, "ExecutionPlan"]: ...

    async def apply_effects(self, view: DAGReadView) -> None: ...


class SnapshotExtension(Protocol[S]):
    @property
    def snapshot_type(self) -> type[S]: ...

    @property
    def contract_id(self) -> ContractId: ...

    @property
    def version(self) -> ContractVersion: ...

    def capture(self) -> S: ...

    async def restore(self, value: S) -> None: ...

    async def validate_restored(self, value: S) -> None: ...


class ExecutionBindings(Protocol):
    def make_node[I: BaseModel, O: BaseModel, E: NodeError](
        self, registration: NodeRegistration[I, O, E],
    ) -> BaseNode[I, O, E]: ...
