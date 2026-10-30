"""Common immutable operation bindings, claims and terminal outcomes; no domain compute."""

from pydantic import TypeAdapter

from app.application.encoding.canonicalCodec import content_digest, encode, decode, merge_manifests
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.application.worldSnapshot.encoding.coreManifest import SNAPSHOT_CORE_SCHEMA
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled, OperationRecord
from app.dataModel.artifacts.lifecycle.operation.claim import PublicationOwner, PublicationBusy, PublicationTerminal, OperationClaim
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import PackActivationResult, PackActivationDisposition, GameplayStarted
from app.db.models.snapshotCore.operationRows import (
    PublicationOperationRow, PublicationRequestRow, PublicationOperationEventRow, PublicationOutcomeRow,
)
from app.db.repositories.sqlite.snapshotCore.commitScope import (
    SqlitePublicationCommitStore, _UID, _HASH, _fields, _wire, _one, _all, _insert, _read_scope, _checked_blob, _write_operation,
)
from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore
from app.db.repositories.sqlite.snapshotCore.publications.playerPublicationStore import SqlitePlayerPublicationStore
from app.ids.deterministicIds import runtime_uid


class SqliteOperationStore:
    def __init__(self, commits: SqlitePublicationCommitStore, world: SqliteWorldPublicationStore,
                 players: SqlitePlayerPublicationStore, manifest=SNAPSHOT_CORE_SCHEMA) -> None:
        self._commits, self._world, self._players = commits, world, players
        self._manifest = merge_manifests(SNAPSHOT_CORE_SCHEMA, manifest)

    async def _event(self, operation_id, scope):
        row = await _one(self._commits, scope,
            "SELECT * FROM publication_operation_events WHERE operation_id=? ORDER BY event_seq DESC LIMIT 1", (operation_id,))
        if row is None:
            raise PublicationInfrastructureError("missing operation lifecycle event")
        _fields(row, uids=("event_id", "operation_id"), optional_uids=("predecessor_id",), positives=("event_seq", "fence"))
        _wire(OperationPhase, row["phase"])
        if row["operation_id"] != operation_id:
            raise PublicationInfrastructureError("event owner mismatch")
        if row["predecessor_id"] is None:
            if row["event_seq"] != 1 or row["fence"] != 1:
                raise PublicationInfrastructureError("invalid operation event root")
        else:
            parent = await _one(self._commits, scope, "SELECT * FROM publication_operation_events WHERE event_id=?", (row["predecessor_id"],))
            if parent is None:
                raise PublicationInfrastructureError("missing operation predecessor")
            _fields(parent, uids=("event_id", "operation_id"), optional_uids=("predecessor_id",), positives=("event_seq", "fence"))
            _wire(OperationPhase, parent["phase"])
            if parent["operation_id"] != operation_id or row["event_seq"] != parent["event_seq"] + 1:
                raise PublicationInfrastructureError("operation chain mismatch")
        return row

    async def _terminal_refs(self, result, scope):
        marker = await _one(self._commits, scope, "SELECT publication_id FROM world_publications WHERE operation_id=?", (result.operation_id,))
        if marker is not None:
            _fields(marker, uids=("publication_id",))
        if isinstance(result, SnapshotApplyResult) and result.category is SnapshotApplyOutcomeKind.COMMITTED:
            actual = None if marker is None else await self._world._by_id(marker["publication_id"], scope)
            refs = result.committed
            if refs is None or actual is None or actual != refs.publication or actual.snapshot_head != refs.world_snapshot:
                raise PublicationInfrastructureError("committed outcome does not match historical publication")
            players = await self._players._for_operation(result.operation_id, scope)
            if players != tuple(sorted(refs.player_snapshots, key=lambda ref: ref.player_uid)):
                raise PublicationInfrastructureError("committed player participants mismatch")
        elif isinstance(result, (PackActivationResult, GameplayStarted)):
            actual = await self._world._by_id(result.publication.publication_id, scope)
            if actual != result.publication:
                raise PublicationInfrastructureError("terminal publication mismatch")
            inactive = isinstance(result, PackActivationResult) and result.disposition is PackActivationDisposition.READY_INACTIVE
            if (inactive and marker is not None) or (not inactive and (marker is None or marker["publication_id"] != actual.publication_id)):
                raise PublicationInfrastructureError("terminal publication disposition mismatch")
        else:
            snapshot = await _one(self._commits, scope, "SELECT snapshot_id FROM world_snapshots WHERE operation_id=?", (result.operation_id,))
            if marker is not None or snapshot is not None or await self._players._for_operation(result.operation_id, scope):
                raise PublicationInfrastructureError("refusal/cancellation cannot hide committed state")

    async def _decode_terminal(self, row, scope):
        _fields(row, uids=("operation_id",), positives=("format_version",), hashes=("outcome_checksum",))
        TypeAdapter(FormatVersion).validate_python(row["format_version"], strict=True)
        if row["format_version"] != 1:
            raise PublicationInfrastructureError("unsupported outcome format")
        expected = {"snapshot_apply": SnapshotApplyResult, "pack_activation": PackActivationResult,
                    "gameplay_start": GameplayStarted, "cancelled": OperationCancelled}.get(row["outcome_kind"])
        if expected is None:
            raise PublicationInfrastructureError("unknown terminal storage discriminator")
        result = decode(_checked_blob(row["outcome_data"], row["outcome_checksum"]), expected, self._manifest)
        category = _wire(SnapshotApplyOutcomeKind, row["category"]) if row["category"] is not None else None
        if result.operation_id != row["operation_id"] or category != (result.category if isinstance(result, SnapshotApplyResult) else None):
            raise PublicationInfrastructureError("terminal row/body mismatch")
        await self._terminal_refs(result, scope)
        return result

    async def _load(self, operation_id, scope) -> OperationRecord | None:
        row = await _one(self._commits, scope, "SELECT * FROM publication_operations WHERE operation_id=?", (operation_id,))
        if row is None:
            return None
        _fields(row, uids=("operation_id", "world_uid"), hashes=("preparation_fingerprint",))
        event = await self._event(operation_id, scope)
        request = await _one(self._commits, scope, "SELECT * FROM publication_requests WHERE operation_id=?", (operation_id,))
        if request is not None:
            _fields(request, uids=("operation_id",), hashes=("publication_fingerprint",))
        terminal = await _one(self._commits, scope, "SELECT * FROM publication_outcomes WHERE operation_id=?", (operation_id,))
        held = await _all(self._commits, scope, """SELECT DISTINCT c.* FROM artifact_catalog c JOIN artifact_holder_events h
            ON h.artifact_id=c.artifact_id WHERE h.holder_kind='operation' AND h.operation_id=? AND h.event_kind='acquire'
            AND NOT EXISTS (SELECT 1 FROM artifact_holder_events n WHERE n.predecessor_id=h.event_id)
            ORDER BY c.kind,c.format_key,c.format_version,c.content_hash""", (operation_id,))
        refs = []
        for artifact in held:
            _fields(artifact, uids=("artifact_id",))
            refs.append(ArtifactRef(kind=_wire(ArtifactKind, artifact["kind"]), format_key=artifact["format_key"],
                format_version=artifact["format_version"], content_hash=artifact["content_hash"],
                nbytes=artifact["nbytes"], row_count=artifact["row_count"]))
        return OperationRecord(operation_id=row["operation_id"], world_uid=row["world_uid"], kind=_wire(OperationKind, row["kind"]),
            preparation_fingerprint=row["preparation_fingerprint"], publication_fingerprint=None if request is None else request["publication_fingerprint"],
            phase=_wire(OperationPhase, event["phase"]), fence=event["fence"], leased_artifacts=tuple(refs),
            terminal=None if terminal is None else await self._decode_terminal(terminal, scope))

    async def read(self, operation_id: EntityUid) -> OperationRecord | None:
        operation_id = _UID.validate_python(operation_id, strict=True)
        async with self._commits._read() as scope:
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
                await _insert(self._commits, scope, PublicationOperationRow(operation_id, world_uid, kind.value, preparation_fingerprint))
                await _insert(self._commits, scope, PublicationRequestRow(operation_id, request_fingerprint))
                await _insert(self._commits, scope, PublicationOperationEventRow(
                    _UID.validate_python(runtime_uid(), strict=True), operation_id, None, 1, OperationPhase.APPLYING.value, 1))
                fence = 1
            else:
                if (record.world_uid != world_uid or record.kind is not kind or record.preparation_fingerprint != preparation_fingerprint
                        or (record.publication_fingerprint is not None and record.publication_fingerprint != request_fingerprint)):
                    raise ValueError("operation identity reused with another immutable binding")
                if record.phase is OperationPhase.TERMINAL:
                    return PublicationTerminal(record=record)
                if record.phase is not OperationPhase.READY:
                    return PublicationBusy(record=record)
                if record.publication_fingerprint is None:
                    await _insert(self._commits, scope, PublicationRequestRow(operation_id, request_fingerprint))
                previous = await self._event(operation_id, scope)
                fence = record.fence
                await _insert(self._commits, scope, PublicationOperationEventRow(_UID.validate_python(runtime_uid(), strict=True),
                    operation_id, previous["event_id"], previous["event_seq"] + 1, OperationPhase.APPLYING.value, fence))
            return PublicationOwner(lease=OperationLeaseRef(operation_id=operation_id, world_uid=world_uid, kind=kind,
                preparation_fingerprint=preparation_fingerprint, fence=fence))

    async def _save(self, scope, outcome):
        operation_id = _write_operation(self._commits, scope)
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
        await self._terminal_refs(outcome, scope)
        data = encode(outcome, self._manifest)
        if isinstance(outcome, SnapshotApplyResult):
            tag, category = OperationKind.SNAPSHOT_APPLY.value, outcome.category.value
        elif isinstance(outcome, PackActivationResult):
            tag, category = OperationKind.PACK_ACTIVATION.value, None
        elif isinstance(outcome, GameplayStarted):
            tag, category = OperationKind.GAMEPLAY_START.value, None
        else:
            tag, category = "cancelled", None
        previous = await self._event(operation_id, scope)
        await _insert(self._commits, scope, PublicationOutcomeRow(operation_id, tag, category, 1, data, content_digest(data).hex()))
        await _insert(self._commits, scope, PublicationOperationEventRow(_UID.validate_python(runtime_uid(), strict=True),
            operation_id, previous["event_id"], previous["event_seq"] + 1, OperationPhase.TERMINAL.value, record.fence))

    async def record_terminal(self, scope: CommitScope, outcome: SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled) -> None:
        self._commits._check(scope, True)
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
