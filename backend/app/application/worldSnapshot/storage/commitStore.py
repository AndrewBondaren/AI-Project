"""Transaction owner port, never injected into domain handlers."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.dataModel.identity.uid import EntityUid


class IPublicationCommitStore(Protocol):
    def transaction(self, operation_id: EntityUid) -> AbstractAsyncContextManager[CommitScope]:
        """Issue one task-bound scope; confirm COMMIT/ROLLBACK on exit, or report unknown outcome."""
        ...
