from dataclasses import dataclass
from time import monotonic
from uuid import UUID, uuid4

from app.application.engine.contracts.invocation.executionStore import Checkpoint, Claim, CloseReceipt, OwnershipConflict
from app.dataModel.engine.dag.identity import ExecutionId, WaitId
from app.dataModel.engine.dag.invocations.record import ExecutionCheckpointStatus, ExecutionStopIntent, InvocationStatus, StopOutcome


@dataclass
class _Entry:
    snapshot: Checkpoint
    owner: str | None = None
    fence: int = 0
    lease_until: float = 0


class MemoryExecutionStore:
    def __init__(self) -> None:
        self._store_id = uuid4()
        self._entries: dict[ExecutionId, _Entry] = {}

    async def get_store_id(self) -> UUID:
        return self._store_id

    async def create(self, execution_id: ExecutionId, blob: bytes) -> None:
        self._entries.setdefault(execution_id, _Entry(Checkpoint(0, InvocationStatus.READY, blob)))

    async def load(self, execution_id: ExecutionId) -> Checkpoint:
        return self._entries[execution_id].snapshot

    async def claim(self, execution_id: ExecutionId, owner_id: str, seconds: int) -> Claim:
        entry = self._entries[execution_id]
        if not owner_id or seconds <= 0:
            raise ValueError("claim requires an owner and positive duration")
        if entry.snapshot.final_revision is not None or (entry.owner is not None and entry.lease_until > monotonic()):
            raise OwnershipConflict(execution_id)
        entry.owner = owner_id
        entry.fence += 1
        entry.lease_until = monotonic() + seconds
        return Claim(execution_id, owner_id, entry.fence)

    def _owned(self, claim: Claim) -> _Entry:
        entry = self._entries[claim.execution_id]
        if (entry.owner, entry.fence) != (claim.owner_id, claim.fence):
            raise OwnershipConflict(claim.execution_id)
        return entry

    async def record_stop_intent(self, claim: Claim, revision: int, outcome: StopOutcome) -> ExecutionStopIntent:
        entry = self._owned(claim)
        saved = entry.snapshot
        if entry.lease_until <= monotonic():
            raise OwnershipConflict(claim.execution_id)
        if saved.stop_intent is not None:
            return saved.replay_stop(revision, outcome)
        if saved.revision != revision:
            raise OwnershipConflict(claim.execution_id)
        intent = ExecutionStopIntent(store_id=self._store_id, execution_id=claim.execution_id,
                                     stop_revision=revision + 1, outcome=outcome)
        entry.snapshot = Checkpoint(revision + 1, saved.status, saved.blob, intent)
        return intent

    async def finalize(self, claim: Claim, revision: int, closed: CloseReceipt) -> Checkpoint:
        entry = self._owned(claim)
        saved = entry.snapshot
        intent = saved.confirm_closed(revision, closed)
        if entry.lease_until <= monotonic():
            raise OwnershipConflict(claim.execution_id)
        entry.snapshot = Checkpoint(revision + 1, saved.status, saved.blob, intent, revision + 1)
        return entry.snapshot

    async def checkpoint(self, claim: Claim, revision: int, status: ExecutionCheckpointStatus, blob: bytes) -> int:
        entry = self._owned(claim)
        if entry.snapshot.stop_intent is not None or entry.snapshot.revision != revision or entry.lease_until <= monotonic():
            raise OwnershipConflict(claim.execution_id)
        entry.snapshot = Checkpoint(revision + 1, status, blob)
        return revision + 1

    async def renew(self, claim: Claim, seconds: int) -> None:
        entry = self._owned(claim)
        if seconds <= 0:
            raise ValueError("lease duration must be positive")
        if entry.snapshot.stop_intent is not None and entry.lease_until <= monotonic():
            raise OwnershipConflict(claim.execution_id)
        entry.lease_until = monotonic() + seconds

    async def cancel_child(self, execution_id: ExecutionId, revision: int, wait_id: WaitId) -> bool:
        entry = self._entries[execution_id]
        if entry.snapshot.stop_intent is not None or entry.snapshot.revision != revision:
            return False
        entry.snapshot = entry.snapshot.with_cancelled_child(wait_id)
        return True

    async def cancel(self, execution_id: ExecutionId, revision: int, blob: bytes) -> bool:
        entry = self._entries[execution_id]
        if entry.snapshot.stop_intent is not None or entry.snapshot.revision != revision:
            return False
        entry.snapshot = Checkpoint(revision + 1, InvocationStatus.CANCELLED, blob)
        entry.fence += 1
        entry.owner = None
        entry.lease_until = 0
        return True

    async def release(self, claim: Claim) -> None:
        self._owned(claim).owner = None
