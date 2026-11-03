from dataclasses import dataclass
from time import monotonic

from app.application.engine.contracts.invocation.executionStore import Checkpoint, Claim, OwnershipConflict
from app.dataModel.engine.dag.identity import ExecutionId


@dataclass
class _Entry:
    snapshot: Checkpoint
    owner: str | None = None
    fence: int = 0
    lease_until: float = 0


class MemoryExecutionStore:
    def __init__(self) -> None:
        self._entries: dict[ExecutionId, _Entry] = {}

    async def create(self, execution_id: ExecutionId, blob: bytes) -> None:
        self._entries.setdefault(execution_id, _Entry(Checkpoint(0, "READY", blob)))

    async def load(self, execution_id: ExecutionId) -> Checkpoint:
        return self._entries[execution_id].snapshot

    async def claim(self, execution_id: ExecutionId, owner_id: str, seconds: int) -> Claim:
        entry = self._entries[execution_id]
        if not owner_id or seconds <= 0:
            raise ValueError("claim requires an owner and positive duration")
        if entry.owner is not None and entry.lease_until > monotonic():
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

    async def checkpoint(self, claim: Claim, revision: int, status: str, blob: bytes) -> int:
        entry = self._owned(claim)
        if entry.snapshot.revision != revision or entry.lease_until <= monotonic():
            raise OwnershipConflict(claim.execution_id)
        entry.snapshot = Checkpoint(revision + 1, status, blob)
        return revision + 1

    async def renew(self, claim: Claim, seconds: int) -> None:
        entry = self._owned(claim)
        if seconds <= 0:
            raise ValueError("lease duration must be positive")
        if entry.lease_until <= monotonic():
            raise OwnershipConflict(claim.execution_id)
        entry.lease_until = monotonic() + seconds

    async def release(self, claim: Claim) -> None:
        self._owned(claim).owner = None
