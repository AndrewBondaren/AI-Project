"""Persistent lease/fence bookkeeping and writer claims; no scheduler or TTL inference."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex


class IArtifactLeases(Protocol):
    async def open_operation(self, operation_id: EntityUid, world_uid: EntityUid, kind: OperationKind,
                             preparation_fingerprint: RevisionHex) -> OperationLeaseRef: ...
    async def assert_writable(self, lease: OperationLeaseRef) -> None: ...
    def writer(self, reservation: StagingReservation) -> AbstractAsyncContextManager[None]:
        """Acquire/release a fenced writer claim; cancel must drain claims before release."""
        ...
    async def finish_preparation(self, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord:
        """Atomically verify the full sealed/held set and close writer admission."""
        ...
    async def recover(self, operation_id: EntityUid) -> OperationRecord:
        """Read terminal/commit markers before permitting an explicit fenced resume."""
        ...
    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord:
        """Prove no publication, close admission and drain claims before cancelling."""
        ...
