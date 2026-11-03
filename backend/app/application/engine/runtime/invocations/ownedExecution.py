from dataclasses import dataclass

from app.application.engine.contracts.invocation.executionStore import Claim, ExecutionStore
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.dataModel.engine.dag.invocations.record import InvocationGraph


@dataclass
class OwnedExecution:
    store: ExecutionStore
    claim: Claim
    revision: int
    graph: InvocationGraph
    lease_seconds: int

    async def save(self) -> None:
        await self.store.renew(self.claim, self.lease_seconds)
        status = "COMPLETED" if self.graph.response is not None else self.graph.records[self.graph.root].status.value
        self.revision = await self.store.checkpoint(self.claim, self.revision, status, CheckpointCodec.encode(self.graph))
