"""Explicit operation bookkeeping; storage owns transitions and transactions."""

from pydantic import TypeAdapter
from app.application.artifacts.storage.artifactLeases import IArtifactLeases
from app.application.publication.contracts.operationStore import IOperationStore
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.dataModel.artifacts.lifecycle.operation.claim import OperationClaim, PublicationOwner
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord, OperationCancelled
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.publication import PackActivationResult, GameplayStarted


class OperationLedger:
    def __init__(self, operations: IOperationStore, leases: IArtifactLeases) -> None:
        self._operations, self._leases = operations, leases

    async def read(self, operation_id: EntityUid) -> OperationRecord | None:
        operation_id = TypeAdapter(EntityUid).validate_python(operation_id, strict=True)
        return await self._operations.read(operation_id)

    async def claim_publication(self, kind: OperationKind, operation_id: EntityUid, world_uid: EntityUid,
                                preparation_fingerprint: RevisionHex, request_fingerprint: RevisionHex) -> OperationClaim:
        return await self._operations.claim_publication(kind, operation_id, world_uid,
                                                        preparation_fingerprint, request_fingerprint)

    async def record_terminal(self, scope: CommitScope,
            outcome: SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled) -> None:
        await self._operations.record_terminal(scope, outcome)

    async def record_refusal(self, claim: PublicationOwner, outcome: SnapshotApplyResult) -> None:
        await self._operations.record_refusal(claim, outcome)

    async def recover(self, operation_id: EntityUid) -> OperationRecord:
        record = await self.read(operation_id)
        if record is not None and record.terminal is not None:
            return record
        return await self._leases.recover(operation_id)

    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord:
        operation_id = TypeAdapter(EntityUid).validate_python(operation_id, strict=True)
        if type(fence) is not int or fence < 1:
            raise ValueError("fence must be a positive integer")
        return await self._leases.cancel(operation_id, fence)
