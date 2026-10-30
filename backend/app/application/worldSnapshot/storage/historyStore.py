"""Metadata/history only; section payload storage remains domain owned."""

from typing import Protocol
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import SnapshotEnvelope


class ISnapshotHistoryStore(Protocol):
    async def append(self, scope: CommitScope, metadata: SnapshotEnvelope,
                     receipts: tuple[SectionApplyReceipt, ...]) -> None: ...

    async def read(self, ref: SnapshotRef, *, scope: CommitReadScope | None = None) -> SnapshotEnvelope | None:
        """When supplied, use the pinned transaction; never open a competing UOW."""
        ...
