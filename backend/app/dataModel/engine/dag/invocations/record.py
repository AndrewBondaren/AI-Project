from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic
from app.dataModel.engine.dag.identity import (
    CallKey, ContractIdValue, ContractVersionValue, ExecutionIdValue, ExecutionIdentity,
    InvocationId, NodeIdValue, PlanInstanceId, PlanRevisionValue,
)
from app.dataModel.engine.dag.invocations.inputWait import InteractionOwner, SavedWait
from app.dataModel.engine.dag.identity import WaitId
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence


class InvocationStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_INPUT = "WAITING_INPUT"
    WAITING_CALLS = "WAITING_CALLS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvocationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)
    execution_id: ExecutionIdValue
    invocation_id: InvocationId
    node_id: NodeIdValue
    plan_instance_id: PlanInstanceId
    caller_invocation_id: InvocationId | None = None
    caller_step: int | None = Field(default=None, ge=0)
    call_key: CallKey | None = None
    contract_id: ContractIdValue
    version: ContractVersionValue
    input: str | None = None
    state_contract: tuple[ContractIdValue, ContractVersionValue] | None = None
    continuation: str | None = None
    step_index: int = Field(default=0, ge=0)
    status: InvocationStatus = InvocationStatus.READY
    plan_revision: PlanRevisionValue
    step_attempts: int = Field(default=0, ge=0)
    attempt_counter: int = Field(default=0, ge=0)
    dependency_bindings: tuple[InvocationId, ...] = ()
    diagnostics: tuple[ExecutionDiagnostic, ...] = ()
    gate_task: str | None = None
    gate_reason: str | None = None
    terminal: str | None = None
    error_index: int | None = Field(default=None, ge=0)
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()

    def accepts_reads(self, reads: tuple[DependencyRead, ...]) -> bool:
        return all(read.result is None or (
            read.result.execution_id == self.execution_id and read.result.invocation_id in self.dependency_bindings
        ) for read in reads)

    def terminal_payload(self) -> str:
        if self.terminal is None:
            raise ValueError("missing terminal payload")
        return self.terminal

    def identity(self) -> ExecutionIdentity:
        return ExecutionIdentity(execution_id=self.execution_id, invocation_id=self.invocation_id,
                                 node_id=self.node_id, attempt=self.attempt_counter, plan_revision=self.plan_revision)


class RegisteredContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    node_id: NodeIdValue
    contract_id: ContractIdValue
    version: ContractVersionValue
    continuation: tuple[ContractIdValue, ContractVersionValue] | None
    input_wait: tuple[ContractIdValue, ContractVersionValue] | None = None


class InvocationGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    execution_id: ExecutionIdValue
    revision: PlanRevisionValue
    root: InvocationId
    session: str | None = None
    response: str | None = None
    interaction_owner: InteractionOwner | None = None
    waits: dict[WaitId, SavedWait] = Field(default_factory=dict[WaitId, SavedWait])
    cancellation: str | None = None
    failure: str | None = None
    waiting_for_input: bool = False
    pass_number: int = Field(default=0, ge=0)
    registry: tuple[RegisteredContract, ...]
    records: dict[InvocationId, InvocationRecord]

    def checkpoint_status(self) -> str:
        if self.cancellation is not None:
            return "CANCELLED"
        if self.failure is not None:
            return "FAILED"
        if self.response is not None:
            return "COMPLETED"
        return "WAITING_INPUT" if self.waiting_for_input else self.records[self.root].status.value

    def cancel_wait(self, child: InvocationRecord) -> None:
        if child.caller_invocation_id is None or child.status != InvocationStatus.WAITING_INPUT:
            raise ValueError("cancellation requires a child waiting for input")
        child.status = InvocationStatus.CANCELLED
        if self.join_complete(self.records[child.caller_invocation_id]):
            self.waiting_for_input = False

    def join_complete(self, caller: InvocationRecord) -> bool:
        return caller.status == InvocationStatus.WAITING_CALLS and all(
            child.status in (InvocationStatus.SUCCEEDED, InvocationStatus.FAILED, InvocationStatus.CANCELLED)
            for child in self.records.values()
            if child.caller_invocation_id == caller.invocation_id and child.caller_step == caller.step_index
        )
