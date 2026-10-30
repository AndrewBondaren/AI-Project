"""Integration ports; concrete requests, effects and policy belong to GEN."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.identity import ContractId, ContractVersion

O = TypeVar("O", bound=BaseModel, covariant=True)
E = TypeVar("E", bound=BaseModel)


@dataclass(frozen=True)
class ResolveResult(Generic[O]):
    ok: bool
    data: O | None = None
    error: str | None = None


class ResponseBinding(Protocol[O]):
    def resolve(self, view: DAGReadView) -> ResolveResult[O]: ...


class TransitionBinding(Protocol):
    def transition(self, view: DAGReadView) -> TaskType | None: ...


class SnapshotExtension(Protocol[E]):
    @property
    def contract_id(self) -> ContractId: ...

    @property
    def version(self) -> ContractVersion: ...

    def capture(self) -> E: ...

    async def restore(self, value: E) -> None: ...

    async def validate_restored(self, value: E) -> None: ...


class ExecutionBindings(Protocol):
    def make_node[I: BaseModel, O: BaseModel](
        self, registration: NodeRegistration[I, O],
    ) -> BaseNode[I, O]: ...
