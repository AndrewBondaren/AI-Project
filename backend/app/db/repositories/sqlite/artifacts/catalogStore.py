"""Immutable artifact identities and storage facts; physical IO stays in backends."""

from contextlib import AbstractAsyncContextManager
from pydantic import TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatKey
from app.dataModel.artifacts.lifecycle.gc import ArtifactStorageEventKind
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationPhase
from app.dataModel.identity.uid import EntityUid
from app.db.models.artifacts.catalogRows import ArtifactCatalogRow, ArtifactStorageEventRow
from app.db.models.artifacts.leaseRows import ArtifactLeaseEventRow, ArtifactWriterClaimRow
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts
from app.db.repositories.sqlite.snapshotCore.operations.operationStore import SqliteOperationStore
from app.db.repositories.sqlite.shared.validation.rowValues import _values, _wire
from app.ids.deterministicIds import runtime_uid


class SqliteArtifactCatalog:
    """SQLite catalog/storage-fact adapter, not a lifecycle orchestrator.

    Keep SQL and integrity checks for this port here; delegate transaction
    mechanics and holder writes to their owners. Do not add planning,
    materialization, backend IO, writer lifecycle, cancel/drain or recovery.
    4C3-B review gate: audit the lease/writer chain checks against these
    ownership boundaries; passing tests alone does not close this gate.
    """

    def __init__(self, scopes: SqliteArtifactScope, operations: SqliteOperationStore,
                 artifacts: SqliteOperationArtifacts) -> None:
        if (operations._commits is not scopes.commits or operations._access is not scopes.access
                or artifacts._access is not scopes.access or operations._artifacts is not artifacts):
            raise ValueError("artifact adapters must share coordinator/access/artifact reader")
        self._scopes, self._operations, self._artifacts = scopes, operations, artifacts
        self._access = scopes.access

    def guard(self, ref: ArtifactRef) -> AbstractAsyncContextManager[None]:
        return self._scopes.guard(ref)

    @staticmethod
    def _descriptor(row: ArtifactCatalogRow) -> ArtifactRef:
        _values(uids=(row.artifact_id,))
        try:
            return ArtifactRef(kind=_wire(ArtifactKind, row.kind), format_key=TypeAdapter(ArtifactFormatKey).validate_python(row.format_key, strict=True),
                format_version=row.format_version, content_hash=row.content_hash,
                nbytes=row.nbytes, row_count=row.row_count)
        except (ValueError, TypeError) as error:
            raise PublicationInfrastructureError("invalid persisted artifact descriptor") from error

    async def _find(self, scope: CommitReadScope | CommitScope, ref: ArtifactRef) -> ArtifactCatalogRow | None:
        row = await self._access.one_row(scope, ArtifactCatalogRow, """SELECT * FROM artifact_catalog
            WHERE kind=? AND format_key=? AND format_version=? AND content_hash=?""",
            (ref.kind.value, ref.format_key, ref.format_version, ref.content_hash))
        if row is not None and self._descriptor(row) != ref:
            raise ValueError("artifact identity reused with another descriptor")
        return row

    async def _by_id(self, scope: CommitReadScope | CommitScope, artifact_id: EntityUid) -> ArtifactRef:
        row = await self._access.one_row(scope, ArtifactCatalogRow,
            "SELECT * FROM artifact_catalog WHERE artifact_id=?", (artifact_id,))
        if row is None or row.artifact_id != artifact_id:
            raise PublicationInfrastructureError("missing or mismatched artifact identity")
        return self._descriptor(row)

    async def _storage(self, scope: CommitReadScope | CommitScope,
                       artifact_id: EntityUid) -> ArtifactStorageEventRow | None:
        rows = await self._access.all_rows(scope, ArtifactStorageEventRow,
            "SELECT * FROM artifact_storage_events WHERE artifact_id=? ORDER BY event_seq", (artifact_id,))
        previous = None
        for row in rows:
            _values(uids=(row.event_id, row.artifact_id), optional_uids=(row.predecessor_id,), positives=(row.event_seq,))
            kind = _wire(ArtifactStorageEventKind, row.kind)
            if (row.artifact_id != artifact_id or row.event_seq != (1 if previous is None else previous.event_seq + 1)
                    or row.predecessor_id != (None if previous is None else previous.event_id)
                    or (previous is None and kind is not ArtifactStorageEventKind.SEALED)
                    or (previous is not None and row.kind == previous.kind)):
                raise PublicationInfrastructureError("invalid artifact storage chain")
            previous = row
        return previous

    async def _lease(self, scope: CommitReadScope | CommitScope, lease: OperationLeaseRef,
                     *, writable: bool) -> None:
        try:
            record = await self._operations._load(lease.operation_id, scope)
        except (ValueError, TypeError) as error:
            raise PublicationInfrastructureError("invalid persisted operation binding") from error
        if record is None or OperationLeaseRef(operation_id=record.operation_id, world_uid=record.world_uid,
                kind=record.kind, preparation_fingerprint=record.preparation_fingerprint, fence=record.fence) != lease:
            raise ValueError("missing or stale operation lease")
        # The existing mapper turns a SQL bool into Python bool; reject malformed raw
        # values by predicate before typed hydration, without raw field access.
        malformed = await self._access.all_rows(scope, ArtifactLeaseEventRow, """SELECT * FROM artifact_lease_events
            WHERE operation_id=? AND (typeof(admission_open)!='integer' OR admission_open NOT IN (0,1))""", (lease.operation_id,))
        if malformed:
            raise PublicationInfrastructureError("invalid raw lease admission boolean")
        rows = await self._access.all_rows(scope, ArtifactLeaseEventRow,
            "SELECT * FROM artifact_lease_events WHERE operation_id=? ORDER BY event_seq", (lease.operation_id,))
        previous = None
        for row in rows:
            _values(uids=(row.event_id, row.operation_id), optional_uids=(row.predecessor_id,), positives=(row.event_seq, row.fence))
            if (row.operation_id != lease.operation_id or row.fence > record.fence
                    or row.event_seq != (1 if previous is None else previous.event_seq + 1)
                    or row.predecessor_id != (None if previous is None else previous.event_id)
                    or (previous is None and (row.fence != 1 or not row.admission_open))
                    or (previous is not None and (row.fence < previous.fence
                        or (not previous.admission_open and row.admission_open)))):
                raise PublicationInfrastructureError("invalid lease admission chain")
            previous = row
        if writable and (record.phase is not OperationPhase.PREPARING or previous is None
                or not previous.admission_open or previous.fence != lease.fence):
            raise ValueError("writer admission is closed or fenced")
        if not writable and (previous is None or previous.admission_open or previous.fence != lease.fence):
            raise ValueError("operation holds require closed admission")

    async def _writers(self, scope: CommitReadScope | CommitScope,
                       operation_id: EntityUid | None = None, artifact_id: EntityUid | None = None) -> tuple[ArtifactWriterClaimRow, ...]:
        rows = await self._access.all_rows(scope, ArtifactWriterClaimRow, """SELECT * FROM artifact_writer_claims
            WHERE (? IS NULL OR operation_id=?) AND (? IS NULL OR artifact_id=?)
            ORDER BY artifact_id,operation_id,fence,event_seq""", (operation_id, operation_id, artifact_id, artifact_id))
        latest: dict[tuple[str, str, int], ArtifactWriterClaimRow] = {}
        for row in rows:
            _values(uids=(row.event_id, row.artifact_id, row.operation_id),
                optional_uids=(row.predecessor_id,), positives=(row.event_seq, row.fence))
            key = (row.artifact_id, row.operation_id, row.fence)
            previous = latest.get(key)
            if (row.event_kind not in ("acquire", "release")
                    or row.event_seq != (1 if previous is None else previous.event_seq + 1)
                    or row.predecessor_id != (None if previous is None else previous.event_id)
                    or (previous is None and row.event_kind != "acquire")
                    or (previous is not None and row.event_kind == previous.event_kind)):
                raise PublicationInfrastructureError("invalid writer claim chain")
            latest[key] = row
        return tuple(row for row in latest.values() if row.event_kind == "acquire")

    async def read(self, ref: ArtifactRef) -> ArtifactRef | None:
        ref = ArtifactRef.model_validate(ref, strict=True)
        async with self._scopes.read_scope() as scope:
            row = await self._find(scope, ref)
            return None if row is None else self._descriptor(row)

    async def reserve(self, lease: OperationLeaseRef, descriptor: ArtifactRef) -> StagingReservation:
        from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        descriptor = ArtifactRef.model_validate(descriptor, strict=True)
        async with self._scopes.transaction(lease.operation_id) as scope:
            await self._lease(scope, lease, writable=True)
            row = await self._find(scope, descriptor)
            if row is None:
                row = ArtifactCatalogRow(runtime_uid(), descriptor.kind.value, descriptor.format_key,
                    descriptor.format_version, descriptor.content_hash, descriptor.nbytes, descriptor.row_count)
                self._descriptor(row)
                await self._access.insert(scope, row)
            # Holder SQL remains owned by the holder adapter, also for atomic reserve.
            await SqliteArtifactHolders._operation_hold(self._access, scope, row.artifact_id, lease)
            return StagingReservation(artifact_id=row.artifact_id, lease=lease, ref=descriptor)

    async def seal(self, reservation: StagingReservation) -> ArtifactRef:
        from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
        reservation = StagingReservation.model_validate(reservation, strict=True)
        async with self._scopes.transaction(reservation.lease.operation_id) as scope:
            row = await self._find(scope, reservation.ref)
            if row is None or row.artifact_id != reservation.artifact_id:
                raise ValueError("reservation identity mismatch")
            await self._lease(scope, reservation.lease, writable=True)
            claims = await self._writers(scope, artifact_id=row.artifact_id)
            if not any(c.operation_id == reservation.lease.operation_id and c.fence == reservation.lease.fence for c in claims):
                raise ValueError("seal requires the reservation's live writer")
            holds = await SqliteArtifactHolders._chain(self._access, scope, row.artifact_id)
            if not any(h.event_kind == "acquire" and h.operation_id == reservation.lease.operation_id
                    and h.fence == reservation.lease.fence for h in holds):
                raise ValueError("seal requires the reservation's hold")
            previous = await self._storage(scope, row.artifact_id)
            if previous is None or previous.kind != ArtifactStorageEventKind.SEALED.value:
                await self._access.insert(scope, ArtifactStorageEventRow(runtime_uid(), row.artifact_id,
                    None if previous is None else previous.event_id, 1 if previous is None else previous.event_seq + 1,
                    ArtifactStorageEventKind.SEALED.value))
            return reservation.ref

    async def is_sealed(self, ref: ArtifactRef) -> bool:
        ref = ArtifactRef.model_validate(ref, strict=True)
        async with self._scopes.read_scope() as scope:
            row = await self._find(scope, ref)
            previous = None if row is None else await self._storage(scope, row.artifact_id)
            return previous is not None and previous.kind == ArtifactStorageEventKind.SEALED.value

    async def mark_deleted(self, ref: ArtifactRef) -> None:
        from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
        ref = ArtifactRef.model_validate(ref, strict=True)
        async with self._scopes.transaction(runtime_uid()) as scope:
            row = await self._find(scope, ref)
            if row is None:
                raise ValueError("unknown artifact")
            holds = await SqliteArtifactHolders._chain(self._access, scope, row.artifact_id)
            if any(h.event_kind == "acquire" for h in holds) or await self._writers(scope, artifact_id=row.artifact_id):
                raise ValueError("GC cannot delete held content or live writers")
            previous = await self._storage(scope, row.artifact_id)
            if previous is not None and previous.kind != ArtifactStorageEventKind.GC_DELETED.value:
                await self._access.insert(scope, ArtifactStorageEventRow(runtime_uid(), row.artifact_id,
                    previous.event_id, previous.event_seq + 1, ArtifactStorageEventKind.GC_DELETED.value))
