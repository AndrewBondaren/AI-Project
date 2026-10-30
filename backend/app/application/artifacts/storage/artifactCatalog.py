"""Catalog identity and shared per-artifact guard; no filesystem or SQL mapping."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation


class IArtifactCatalog(Protocol):
    def guard(self, ref: ArtifactRef) -> AbstractAsyncContextManager[None]:
        """Serialize reserve/seal/holders/writers/GC checks using the same storage guard."""
        ...
    async def read(self, ref: ArtifactRef) -> ArtifactRef | None: ...
    async def reserve(self, lease: OperationLeaseRef, descriptor: ArtifactRef) -> StagingReservation:
        """Deduplicate identity; atomically check lease/fence and acquire its hold."""
        ...
    async def seal(self, reservation: StagingReservation) -> ArtifactRef:
        """Record durable verification only under the current writer/fence guard."""
        ...
    async def is_sealed(self, ref: ArtifactRef) -> bool: ...
    async def mark_deleted(self, ref: ArtifactRef) -> None:
        """Append the storage fact after guarded deletion; never delete catalog history."""
        ...
