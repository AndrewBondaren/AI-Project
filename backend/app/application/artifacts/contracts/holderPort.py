"""Shared live-set and transactional handoff port for staged/published content."""

from typing import Protocol
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.holders import ArtifactHolderRef
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef


class IArtifactHolders(Protocol):
    async def acquire(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> None: ...
    async def release(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> None:
        """Operation holds require closed writer admission and drained claims before release."""
        ...
    async def holders(self, ref: ArtifactRef) -> tuple[ArtifactHolderRef, ...]: ...
    async def is_held(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> bool: ...
    async def handoff(self, scope: CommitScope, lease: OperationLeaseRef,
                      snapshots: tuple[SnapshotRef, ...], retained_refs: tuple[ArtifactRef, ...]) -> None:
        """Acquire published holds and release only transferred operation refs atomically."""
        ...
