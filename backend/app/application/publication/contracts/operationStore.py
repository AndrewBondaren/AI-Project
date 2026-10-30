"""Common claims/outcomes port, separate from domain storage and transaction ownership."""

from typing import Protocol
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.dataModel.artifacts.lifecycle.operation.claim import OperationClaim, PublicationOwner
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled, OperationRecord
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.publication import GameplayStarted, PackActivationResult


class IOperationStore(Protocol):
    async def claim_publication(self, kind: OperationKind, operation_id: EntityUid, world_uid: EntityUid,
                                preparation_fingerprint: RevisionHex, request_fingerprint: RevisionHex) -> OperationClaim:
        """Short atomic bookkeeping claim; no domain writes or hidden retry."""
        ...
    async def read(self, operation_id: EntityUid) -> OperationRecord | None: ...
    async def record_terminal(self, scope: CommitScope,
                              outcome: SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled) -> None:
        """Same publication transaction as world/player/history/holders."""
        ...
    async def record_refusal(self, claim: PublicationOwner, outcome: SnapshotApplyResult) -> None:
        """Only CONFLICT/REJECTED, after confirmed rollback; never on unknown COMMIT."""
        ...
