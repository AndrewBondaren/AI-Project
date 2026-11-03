from dataclasses import dataclass

from app.application.engine.contracts.invocation.executionStore import Claim, ExecutionStore, OwnershipConflict
from app.application.engine.contracts.invocation.inputWait import InputConflict
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationStatus


@dataclass
class OwnedExecution:
    store: ExecutionStore
    claim: Claim
    revision: int
    graph: InvocationGraph
    lease_seconds: int

    async def save(self) -> None:
        while True:
            await self.store.renew(self.claim, self.lease_seconds)
            try:
                self.revision = await self.store.checkpoint(
                    self.claim, self.revision, self.graph.checkpoint_status(), CheckpointCodec.encode(self.graph),
                )
                return
            except OwnershipConflict:
                saved = await self.store.load(self.claim.execution_id)
                if saved.revision <= self.revision:
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
