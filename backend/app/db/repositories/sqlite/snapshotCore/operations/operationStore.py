"""Common immutable operation bindings, claims and terminal outcomes; no domain compute."""

from pydantic import TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled, OperationRecord
from app.dataModel.artifacts.lifecycle.operation.claim import PublicationOwner, PublicationBusy, PublicationTerminal, OperationClaim
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import PackActivationResult, GameplayStarted
from app.db.models.snapshotCore.operationRows import (
    PublicationOperationRow, PublicationRequestRow, PublicationOperationEventRow, PublicationOutcomeRow,
)
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _UID, _HASH, _values, _wire
from app.ids.deterministicIds import runtime_uid


from app.db.repositories.sqlite.snapshotCore.operations.terminalCodec import StoredTerminalCodec
from app.db.repositories.sqlite.snapshotCore.operations.publicationEvidence import SqlitePublicationEvidence
from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts


class SqliteOperationStore:
    def __init__(self, commits: SqlitePublicationCommitStore, access: ScopedSqliteAccess,
                 codec: StoredTerminalCodec, evidence: SqlitePublicationEvidence,
                 artifacts: SqliteOperationArtifacts) -> None:
        if (access.registry is not commits.registry or evidence._commits is not commits
                or evidence._access is not access or artifacts._access is not access):
            raise ValueError("operation dependencies must share one commit coordinator and access")
        self._access, self._registry, self._commits = access, access.registry, commits
        self._codec, self._evidence, self._artifacts = codec, evidence, artifacts

    async def _event(self, operation_id: EntityUid, scope: CommitReadScope | CommitScope) -> PublicationOperationEventRow:
        row = await self._access.one_row(scope, PublicationOperationEventRow,
            "SELECT * FROM publication_operation_events WHERE operation_id=? ORDER BY event_seq DESC LIMIT 1", (operation_id,))
        if row is None:
            raise PublicationInfrastructureError("missing operation lifecycle event")
        _values(uids=(row.event_id, row.operation_id), optional_uids=(row.predecessor_id,), positives=(row.event_seq, row.fence))
        phase = _wire(OperationPhase, row.phase)
        if row.operation_id != operation_id:
            raise PublicationInfrastructureError("event owner mismatch")
        if row.predecessor_id is None:
            if row.event_seq != 1 or row.fence != 1 or phase not in (OperationPhase.PREPARING, OperationPhase.APPLYING):
                raise PublicationInfrastructureError("invalid operation event root")
        else:
            parent = await self._access.one_row(scope, PublicationOperationEventRow, "SELECT * FROM publication_operation_events WHERE event_id=?", (row.predecessor_id,))
            if parent is None:
                raise PublicationInfrastructureError("missing operation predecessor")
            _values(uids=(parent.event_id, parent.operation_id), optional_uids=(parent.predecessor_id,), positives=(parent.event_seq, parent.fence))
            parent_phase = _wire(OperationPhase, parent.phase)
            if parent.operation_id != operation_id or row.event_seq != parent.event_seq + 1:
                raise PublicationInfrastructureError("operation chain mismatch")
            same_fence = row.fence == parent.fence
            allowed = {
                OperationPhase.PREPARING: (OperationPhase.READY, OperationPhase.TERMINAL),
                OperationPhase.READY: (OperationPhase.APPLYING, OperationPhase.TERMINAL),
                OperationPhase.APPLYING: (OperationPhase.RECOVERY_REQUIRED, OperationPhase.TERMINAL),
                OperationPhase.RECOVERY_REQUIRED: (OperationPhase.TERMINAL,),
                OperationPhase.TERMINAL: (),
            }
            resume = (row.fence == parent.fence + 1 and phase is OperationPhase.READY
                      and parent_phase in (OperationPhase.APPLYING, OperationPhase.RECOVERY_REQUIRED))
            if not ((same_fence and phase in allowed[parent_phase]) or resume):
                raise PublicationInfrastructureError("stored operation phase/fence transition mismatch")
        return row

    async def _load(self, operation_id: EntityUid, scope: CommitReadScope | CommitScope) -> OperationRecord | None:
        row = await self._access.one_row(scope, PublicationOperationRow, "SELECT * FROM publication_operations WHERE operation_id=?", (operation_id,))
        if row is None:
            return None
        _values(uids=(row.operation_id, row.world_uid), hashes=(row.preparation_fingerprint,))
        event = await self._event(operation_id, scope)
        request = await self._access.one_row(scope, PublicationRequestRow, "SELECT * FROM publication_requests WHERE operation_id=?", (operation_id,))
        if request is not None:
            _values(uids=(request.operation_id,), hashes=(request.publication_fingerprint,))
        terminal = await self._access.one_row(scope, PublicationOutcomeRow, "SELECT * FROM publication_outcomes WHERE operation_id=?", (operation_id,))
        refs = await self._artifacts.read(scope.read_scope if isinstance(scope, CommitScope) else scope, operation_id)
        result = None if terminal is None else self._codec.decode(terminal)
        if result is not None:
            await self._evidence.check(scope, result)
        return OperationRecord(operation_id=row.operation_id, world_uid=row.world_uid, kind=_wire(OperationKind, row.kind),
            preparation_fingerprint=row.preparation_fingerprint, publication_fingerprint=None if request is None else request.publication_fingerprint,
            phase=_wire(OperationPhase, event.phase), fence=event.fence, leased_artifacts=refs,
            terminal=result)

    async def read(self, operation_id: EntityUid) -> OperationRecord | None:
        operation_id = _UID.validate_python(operation_id, strict=True)
        async with self._commits.read_scope() as scope:
            return await self._load(operation_id, scope)

    async def claim_publication(self, kind: OperationKind, operation_id: EntityUid, world_uid: EntityUid,
                                preparation_fingerprint: RevisionHex, request_fingerprint: RevisionHex) -> OperationClaim:
        kind = TypeAdapter(OperationKind).validate_python(kind, strict=True)
        operation_id = _UID.validate_python(operation_id, strict=True)
        world_uid = _UID.validate_python(world_uid, strict=True)
        preparation_fingerprint = _HASH.validate_python(preparation_fingerprint, strict=True)
        request_fingerprint = _HASH.validate_python(request_fingerprint, strict=True)
        async with self._commits.transaction(operation_id) as scope:
            record = await self._load(operation_id, scope)
            if record is None:
                event_id = _UID.validate_python(runtime_uid(), strict=True)
                await self._access.insert(scope, PublicationOperationRow(operation_id, world_uid, kind.value, preparation_fingerprint))
                await self._access.insert(scope, PublicationRequestRow(operation_id, request_fingerprint))
                await self._access.insert(scope, PublicationOperationEventRow(
                    event_id, operation_id, None, 1, OperationPhase.APPLYING.value, 1))
                fence = 1
            else:
                if (record.world_uid != world_uid or record.kind is not kind or record.preparation_fingerprint != preparation_fingerprint
                        or (record.publication_fingerprint is not None and record.publication_fingerprint != request_fingerprint)):
                    raise ValueError("operation identity reused with another immutable binding")
                if record.phase is OperationPhase.TERMINAL:
                    return PublicationTerminal(record=record)
                if record.phase is not OperationPhase.READY:
                    return PublicationBusy(record=record)
                event_id = _UID.validate_python(runtime_uid(), strict=True)
                if record.publication_fingerprint is None:
                    await self._access.insert(scope, PublicationRequestRow(operation_id, request_fingerprint))
                previous = await self._event(operation_id, scope)
                fence = record.fence
                await self._access.insert(scope, PublicationOperationEventRow(event_id,
                    operation_id, previous.event_id, previous.event_seq + 1, OperationPhase.APPLYING.value, fence))
            return PublicationOwner(lease=OperationLeaseRef(operation_id=operation_id, world_uid=world_uid, kind=kind,
                preparation_fingerprint=preparation_fingerprint, fence=fence))

    async def _save(self, scope, outcome):
        operation_id = self._registry.operation_id(scope)
        record = await self._load(operation_id, scope)
        if record is None or outcome.operation_id != operation_id:
            raise ValueError("terminal operation mismatch")
        if record.terminal is not None:
            if record.terminal != outcome:
                raise ValueError("terminal identity cannot be overwritten")
            return
        if not isinstance(outcome, OperationCancelled) and record.phase is not OperationPhase.APPLYING:
            raise ValueError("publication outcome requires a claimed applying operation")
        OperationRecord.model_validate({**record.model_dump(), "phase": OperationPhase.TERMINAL, "terminal": outcome}, strict=True)
        await self._evidence.check(scope, outcome)
        terminal_row = self._codec.encode(outcome)
        previous = await self._event(operation_id, scope)
        event_id = _UID.validate_python(runtime_uid(), strict=True)
        await self._access.insert(scope, terminal_row)
        await self._access.insert(scope, PublicationOperationEventRow(event_id,
            operation_id, previous.event_id, previous.event_seq + 1, OperationPhase.TERMINAL.value, record.fence))

    async def record_terminal(self, scope: CommitScope, outcome: SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled) -> None:
        self._registry.check(scope, True)
        if type(outcome) not in (SnapshotApplyResult, PackActivationResult, GameplayStarted, OperationCancelled):
            raise TypeError("terminal must be a typed record")
        outcome = type(outcome).model_validate(outcome, strict=True)
        if isinstance(outcome, SnapshotApplyResult) and outcome.category is not SnapshotApplyOutcomeKind.COMMITTED:
            raise ValueError("record refusal only after confirmed rollback through record_refusal")
        await self._save(scope, outcome)

    async def record_refusal(self, claim: PublicationOwner, outcome: SnapshotApplyResult) -> None:
        claim = PublicationOwner.model_validate(claim, strict=True)
        outcome = SnapshotApplyResult.model_validate(outcome, strict=True)
        if outcome.category is SnapshotApplyOutcomeKind.COMMITTED:
            raise ValueError("refusal cannot assert a committed outcome")
        async with self._commits.transaction(claim.lease.operation_id) as scope:
            record = await self._load(claim.lease.operation_id, scope)
            if record is None:
                raise ValueError("missing claimed operation")
            lease = OperationLeaseRef(operation_id=record.operation_id, world_uid=record.world_uid,
                kind=record.kind, preparation_fingerprint=record.preparation_fingerprint, fence=record.fence)
            if lease != claim.lease or record.phase not in (OperationPhase.APPLYING, OperationPhase.TERMINAL):
                raise ValueError("stale or unowned operation claim")
            await self._save(scope, outcome)
