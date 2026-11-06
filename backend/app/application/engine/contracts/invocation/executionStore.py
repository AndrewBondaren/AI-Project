from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.dataModel.engine.dag.identity import ExecutionId, WaitId
from app.dataModel.engine.dag.invocations.record import ExecutionCheckpointStatus, ExecutionStopIntent, InvocationGraph, StopOutcome


class OwnershipConflict(RuntimeError):
    pass


class RestoreFailure(ValueError):
    pass


@dataclass(frozen=True)
class Claim:
    execution_id: ExecutionId
    owner_id: str
    fence: int


@dataclass(frozen=True)
class Checkpoint:
    revision: int
    status: ExecutionCheckpointStatus
    blob: bytes
    stop_intent: ExecutionStopIntent | None = None

    def replay_stop(self, revision: int, outcome: StopOutcome) -> ExecutionStopIntent:
        intent = self.stop_intent
        if (intent is None or self.revision != intent.stop_revision
                or intent.stop_revision != revision + 1 or intent.outcome != outcome):
            raise OwnershipConflict("conflicting stop intent or revision")
        return intent

    def with_cancelled_child(self, wait_id: WaitId) -> "Checkpoint":
        graph = InvocationGraph.model_validate_json(self.blob)
        wait = graph.waits[wait_id]
        child = graph.records[wait.invocation_id]
        if graph.cancellation is not None or wait.accepted is not None or wait.step_index != child.step_index:
            raise ValueError("wait is not cancellable")
        graph.cancel_wait(child)
        return Checkpoint(self.revision + 1, graph.checkpoint_status(), graph.model_dump_json().encode())


class ExecutionStore(Protocol):
    async def get_store_id(self) -> UUID: ...
    async def create(self, execution_id: ExecutionId, blob: bytes) -> None: ...
    async def load(self, execution_id: ExecutionId) -> Checkpoint: ...
    async def claim(self, execution_id: ExecutionId, owner_id: str, seconds: int) -> Claim: ...
    async def record_stop_intent(self, claim: Claim, revision: int, outcome: StopOutcome) -> ExecutionStopIntent: ...
    async def checkpoint(self, claim: Claim, revision: int, status: ExecutionCheckpointStatus, blob: bytes) -> int: ...
    async def cancel_child(self, execution_id: ExecutionId, revision: int, wait_id: WaitId) -> bool:
        """Publish a single validated wait cancellation by revision CAS, preserving the current lease."""
        ...
    async def cancel(self, execution_id: ExecutionId, revision: int, blob: bytes) -> bool:
        """Atomically publish cancellation and revoke the current fence if revision still matches."""
        ...
    async def renew(self, claim: Claim, seconds: int) -> None: ...
    async def release(self, claim: Claim) -> None: ...
