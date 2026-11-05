from asyncio import Lock
from dataclasses import dataclass, field
from typing import Never

from app.application.engine.contracts.invocation.executionStore import Claim, ExecutionStore, OwnershipConflict
from app.application.engine.contracts.invocation.inputWait import InputConflict
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.dataModel.engine.dag.invocations.record import ExecutionStopIntent, InvocationGraph, InvocationStatus, StopOutcome


class ExecutionStopping(RuntimeError):
    """The recovery owner reached the F2 boundary with this durable intent."""

    def __init__(self, intent: ExecutionStopIntent) -> None:
        self.intent = intent
        super().__init__(f"execution {intent.execution_id} stopping at revision {intent.stop_revision}")


@dataclass
class OwnedExecution:
    store: ExecutionStore
    claim: Claim
    revision: int
    graph: InvocationGraph
    lease_seconds: int

    _writes: Lock = field(default_factory=Lock, init=False)

    async def stop(self, outcome: StopOutcome) -> Never:
        async with self._writes:
            intent = await self.store.record_stop_intent(self.claim, self.revision, outcome)
        raise ExecutionStopping(intent)

    async def save(self) -> None:
        async with self._writes:
            await self._checkpoint()

    async def _checkpoint(self) -> None:
        while True:
            blob = CheckpointCodec.encode(self.graph)
            status = self.graph.checkpoint_status()
            await self.store.renew(self.claim, self.lease_seconds)
            try:
                self.revision = await self.store.checkpoint(
                    self.claim, self.revision, status, blob,
                )
                return
            except OwnershipConflict:
                saved = await self.store.load(self.claim.execution_id)
                if saved.stop_intent is not None or saved.revision <= self.revision:
                    raise
                # Only a child cancellation can advance the revision while we still own this fence.
                await self.store.renew(self.claim, self.lease_seconds)
                latest = InvocationGraph.model_validate_json(saved.blob)
                cancelled = [wait for wait in latest.waits.values() if wait.accepted is None
                             and latest.records[wait.invocation_id].status == InvocationStatus.CANCELLED
                             and self.graph.records[wait.invocation_id].status != InvocationStatus.CANCELLED]
                if len(cancelled) != saved.revision - self.revision:
                    raise
                for wait in cancelled:
                    if self.graph.waits[wait.wait_id].accepted is not None:
                        raise InputConflict("child wait was cancelled") from None
                    self.graph.cancel_wait(self.graph.records[wait.invocation_id])
                self.revision = saved.revision
