"""Durable staging admission and writer ownership."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace

from pydantic import TypeAdapter, PositiveInt

from app.application.publication.errors import OperationBusyError, PublicationInfrastructureError
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord, OperationCancellationReason, OperationCancelled
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.db.models.artifacts.leaseRows import ArtifactLeaseEventRow, ArtifactWriterClaimRow
from app.db.models.snapshotCore.operationRows import PublicationOperationEventRow, PublicationOperationRow
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from app.db.repositories.sqlite.artifacts.catalogStore import SqliteArtifactCatalog
from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts
from app.db.repositories.sqlite.snapshotCore.operations.operationStore import SqliteOperationStore
from app.db.repositories.sqlite.shared.validation.rowValues import _UID
from app.ids.deterministicIds import runtime_uid


class SqliteArtifactLeases:
    def __init__(self, scopes: SqliteArtifactScope, operations: SqliteOperationStore,
                 artifacts: SqliteOperationArtifacts) -> None:
        self._catalog = SqliteArtifactCatalog(scopes, operations, artifacts)
        self._scopes, self._operations, self._access = scopes, operations, scopes.access

    def _transaction(self, operation_id):
        self._scopes._require_unbound()
        return self._scopes.commits.transaction(operation_id)

    async def _record(self, scope, operation_id) -> OperationRecord:
        record = await self._operations._load(operation_id, scope)
        if record is None:
            raise ValueError("unknown operation")
        return record

    async def open_operation(self, operation_id: EntityUid, world_uid: EntityUid, kind: OperationKind,
                             preparation_fingerprint: RevisionHex) -> OperationLeaseRef:
        lease = OperationLeaseRef(operation_id=operation_id, world_uid=world_uid, kind=kind,
            preparation_fingerprint=preparation_fingerprint, fence=1)
        async with self._transaction(operation_id) as scope:
            record = await self._operations._load(operation_id, scope)
            if record is None:
                await self._access.insert(scope, PublicationOperationRow(operation_id, world_uid, kind.value, preparation_fingerprint))
                await self._access.insert(scope, PublicationOperationEventRow(runtime_uid(), operation_id, None, 1, "preparing", 1))
                await self._access.insert(scope, ArtifactLeaseEventRow(runtime_uid(), operation_id, None, 1, 1, True))
            else:
                lease = OperationLeaseRef(operation_id=operation_id, world_uid=world_uid, kind=kind,
                    preparation_fingerprint=preparation_fingerprint, fence=record.fence)
                latest = await self._admission(scope, operation_id)
                if latest is None:
                    raise ValueError("operation has no staging lease")
                await self._catalog._lease(scope, lease, writable=latest.admission_open)
        return lease

    async def assert_writable(self, lease: OperationLeaseRef) -> None:
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        async with self._scopes.read_scope() as scope:
            await self._catalog._lease(scope, lease, writable=True)

    async def _release(self, claim, allow_rollback):
        async with self._transaction(claim.operation_id) as scope:
            active = await self._catalog._writers(scope, claim.operation_id, claim.artifact_id)
            if claim not in active and not allow_rollback:
                raise PublicationInfrastructureError("writer lost its acquired claim")
            if claim in active:
                await self._access.insert(scope, replace(claim, event_id=runtime_uid(), predecessor_id=claim.event_id,
                    event_seq=claim.event_seq + 1, event_kind="release"))

    async def _cleanup(self, claim, *, allow_rollback=False):
        task = asyncio.create_task(self._release(claim, allow_rollback))
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    @asynccontextmanager
    async def writer(self, reservation: StagingReservation) -> AsyncIterator[None]:
        reservation = StagingReservation.model_validate(reservation, strict=True)
        lease = reservation.lease
        claim = None
        try:
            async with self._transaction(lease.operation_id) as scope:
                await self._catalog._lease(scope, lease, writable=True)
                if await self._catalog._by_id(scope, reservation.artifact_id) != reservation.ref:
                    raise ValueError("reservation identity mismatch")
                holds = await SqliteArtifactHolders._chain(self._access, scope, reservation.artifact_id)
                if not any(h.operation_id == lease.operation_id and h.fence == lease.fence and h.event_kind == "acquire" for h in holds):
                    raise ValueError("reservation is not held")
                if await self._catalog._writers(scope, lease.operation_id, reservation.artifact_id):
                    raise OperationBusyError("reservation already has a writer")
                previous = await self._access.one_row(scope, ArtifactWriterClaimRow, """SELECT * FROM artifact_writer_claims
                    WHERE artifact_id=? AND operation_id=? AND fence=? ORDER BY event_seq DESC LIMIT 1""",
                    (reservation.artifact_id, lease.operation_id, lease.fence))
                claim = ArtifactWriterClaimRow(runtime_uid(), reservation.artifact_id, lease.operation_id, lease.fence,
                    previous.event_id if previous else None, previous.event_seq + 1 if previous else 1, "acquire")
                await self._access.insert(scope, claim)
        except asyncio.CancelledError:
            # The coordinator can confirm COMMIT and still deliver cancellation.
            if claim is not None:
                await self._cleanup(claim, allow_rollback=True)
            raise
        try:
            yield
        finally:
            await self._cleanup(claim)

    async def _admission(self, scope, operation_id):
        return await self._access.one_row(scope, ArtifactLeaseEventRow, """SELECT * FROM artifact_lease_events
            WHERE operation_id=? ORDER BY event_seq DESC LIMIT 1""", (operation_id,))

    async def _close(self, scope, lease):
        latest = await self._admission(scope, lease.operation_id)
        if latest is None:
            return  # Direct publication has no staging admission.
        await self._catalog._lease(scope, lease, writable=latest.admission_open)
        if latest.admission_open:
            await self._access.insert(scope, replace(latest, event_id=runtime_uid(), predecessor_id=latest.event_id,
                event_seq=latest.event_seq + 1, admission_open=False))

    async def finish_preparation(self, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord:
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        refs = TypeAdapter(tuple[ArtifactRef, ...]).validate_python(refs, strict=True)
        async with self._transaction(lease.operation_id) as scope:
            await self._catalog._lease(scope, lease, writable=True)
            if await self._catalog._writers(scope, lease.operation_id):
                raise OperationBusyError("preparation still has writers")
            record = await self._record(scope, lease.operation_id)
            if len(set(refs)) != len(refs) or set(refs) != set(record.leased_artifacts):
                raise ValueError("prepared refs must match every operation hold exactly once")
            for ref in refs:
                row = await self._catalog._find(scope, ref)
                storage = await self._catalog._storage(scope, row.artifact_id) if row else None
                if storage is None or storage.kind != "sealed":
                    raise ValueError("unsealed prepared artifact")
            await self._close(scope, lease)
            event = await self._operations._event(lease.operation_id, scope)
            await self._access.insert(scope, PublicationOperationEventRow(runtime_uid(), lease.operation_id,
                event.event_id, event.event_seq + 1, "ready", lease.fence))
            return await self._record(scope, lease.operation_id)

    async def recover(self, operation_id: EntityUid) -> OperationRecord:
        operation_id = _UID.validate_python(operation_id, strict=True)
        self._scopes._require_unbound()
        async with self._scopes.commits.read_scope() as scope:
            record = await self._record(scope, operation_id)
            if record.phase in (OperationPhase.APPLYING, OperationPhase.RECOVERY_REQUIRED):
                raise OperationBusyError("publication owner quiescence is unproven")
            return record

    async def cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord:
        fence = TypeAdapter(PositiveInt).validate_python(fence, strict=True)
        outcome = OperationCancelled(operation_id=operation_id, reason=OperationCancellationReason.REQUESTED)
        async with self._transaction(operation_id) as scope:
            record = await self._record(scope, operation_id)
            if record.fence != fence:
                raise ValueError("stale cancellation fence")
            if record.terminal is not None:
                return record
            await self._operations._evidence.check(scope, outcome)
            lease = OperationLeaseRef(operation_id=operation_id, world_uid=record.world_uid, kind=record.kind,
                preparation_fingerprint=record.preparation_fingerprint, fence=fence)
            await self._close(scope, lease)
        while True:
            async with self._scopes.read_scope() as read:
                busy = await self._catalog._writers(read, operation_id)
            if not busy:
                break
            await asyncio.sleep(0.05)
        async with self._transaction(operation_id) as scope:
            record = await self._record(scope, operation_id)
            if record.fence != fence:
                raise ValueError("stale cancellation fence")
            if record.terminal is not None:
                return record
            if await self._catalog._writers(scope, operation_id):
                raise OperationBusyError("operation still has writers")
            for ref in record.leased_artifacts:
                row = await self._catalog._find(scope, ref)
                if row is None:
                    raise PublicationInfrastructureError("missing held artifact")
                holds = await SqliteArtifactHolders._chain(self._access, scope, row.artifact_id)
                for hold in holds:
                    if hold.operation_id == operation_id and hold.event_kind == "acquire":
                        if hold.fence != fence:
                            raise ValueError("operation holds have another fence")
                        await SqliteArtifactHolders._append(self._access, scope, hold, False)
            await self._operations.record_terminal(scope, outcome)
            return await self._record(scope, operation_id)
