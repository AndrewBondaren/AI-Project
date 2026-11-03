from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.dataModel.engine.dag.identity import ContractId, ContractVersion, ExecutionIdentity, Ordinal, WaitIdValue
from app.dataModel.engine.dag.invocations.inputWait import InteractionBinding, InteractionOwner, Reference


@dataclass(frozen=True)
class InputWaitContract[U: BaseModel, M: BaseModel]:
    contract_id: ContractId
    version: ContractVersion
    input_type: type[U]
    intermediate_type: type[M]


@dataclass(frozen=True)
class WaitSpec[U: BaseModel, M: BaseModel]:
    wait_id: WaitIdValue
    contract: InputWaitContract[U, M]
    binding_ref: str
    intermediate: M
    expected_revision: int


@dataclass(frozen=True)
class WaitInput[S: BaseModel, U: BaseModel, M: BaseModel]:
    wait_spec: WaitSpec[U, M]
    state: S


@dataclass(frozen=True)
class InputReceived[U: BaseModel]:
    contract: InputWaitContract[U, BaseModel]
    payload: U

    def get[T: BaseModel](self, contract: InputWaitContract[T, BaseModel]) -> T:
        if contract != self.contract or not isinstance(self.payload, contract.input_type):
            raise TypeError("received input differs from declared contract")
        return self.payload


class ResumeInput[U: BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    wait_id: WaitIdValue
    request_id: Reference
    expected_revision: Ordinal
    payload: U


class InteractionPort(Protocol):
    @property
    def owner(self) -> InteractionOwner: ...
    def bind(self, reference: str, identity: ExecutionIdentity, step: int) -> InteractionBinding: ...
    def authorize(self, binding: InteractionBinding, payload: BaseModel) -> None: ...


@dataclass(frozen=True)
class PendingInput[M: BaseModel]:
    wait_id: WaitIdValue
    expected_revision: int
    intermediate: M


@dataclass(frozen=True)
class Waiting[M: BaseModel]:
    pending: tuple[PendingInput[M], ...]


@dataclass(frozen=True)
class Failed:
    diagnostic: str


class InputConflict(ValueError):
    pass
