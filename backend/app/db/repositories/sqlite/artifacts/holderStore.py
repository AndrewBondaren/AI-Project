"""Typed live-set and atomic holder handoff; never owns a publication commit."""

from dataclasses import replace
from pydantic import TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.holders import (
    ArtifactHolderRef, ArtifactHolderKind, OperationHolder, ArtifactRetentionHolder, SnapshotHolder, PinHolder,
)
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationPhase
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, SnapshotChainKind, WorldSnapshotRef
from app.db.models.artifacts.holderRows import ArtifactHolderEventRow
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from app.db.repositories.sqlite.artifacts.catalogStore import SqliteArtifactCatalog
from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts
from app.db.repositories.sqlite.snapshotCore.operations.operationStore import SqliteOperationStore
from app.db.repositories.sqlite.snapshotCore.history.snapshotHistoryStore import SqliteSnapshotHistoryStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _values, _wire
from app.ids.deterministicIds import runtime_uid


class SqliteArtifactHolders:
    """SQLite holder adapter; handoff is one atomic storage operation.

    Keep holder SQL, owner validation and hold transfer here. The caller owns
    publication order and the borrowed transaction; do not add snapshot
    creation, domain apply, materialization, backend IO or lease lifecycle.
    4C3-B review gate: audit metadata/catalog dependencies for orchestration
    creep; passing tests alone does not close this gate.
    """

    def __init__(self, scopes: SqliteArtifactScope, operations: SqliteOperationStore,
                 artifacts: SqliteOperationArtifacts, history: SqliteSnapshotHistoryStore) -> None:
        self._catalog = SqliteArtifactCatalog(scopes, operations, artifacts)
        if history._commits is not scopes.commits or history._access is not scopes.access:
            raise ValueError("holder/history must share coordinator and access")
        self._scopes, self._operations, self._artifacts, self._history = scopes, operations, artifacts, history
        self._access = scopes.access

    @staticmethod
    def _key(row: ArtifactHolderEventRow) -> tuple[object, ...]:
        return (row.holder_kind, row.operation_id, row.fence, row.retained_artifact_id,
                row.world_snapshot_id, row.player_snapshot_id, row.pin_id)

    @staticmethod
    async def _chain(access: ScopedSqliteAccess, scope: CommitReadScope | CommitScope,
                     artifact_id: EntityUid) -> tuple[ArtifactHolderEventRow, ...]:
        rows = await access.all_rows(scope, ArtifactHolderEventRow,
            "SELECT * FROM artifact_holder_events WHERE artifact_id=? ORDER BY event_seq,event_id", (artifact_id,))
        latest: dict[tuple[object, ...], ArtifactHolderEventRow] = {}
        for row in rows:
            _values(uids=(row.event_id, row.artifact_id), optional_uids=(row.operation_id, row.retained_artifact_id,
                row.world_snapshot_id, row.player_snapshot_id, row.pin_id, row.predecessor_id),
                positives=(row.event_seq,) if row.fence is None else (row.event_seq, row.fence))
            kind = _wire(ArtifactHolderKind, row.holder_kind)
            if kind is ArtifactHolderKind.OPERATION:
                valid = (row.operation_id is not None and row.fence is not None and row.retained_artifact_id is None
                    and row.world_snapshot_id is None and row.player_snapshot_id is None)
            elif kind is ArtifactHolderKind.ARTIFACT:
                valid = (row.retained_artifact_id is not None and row.operation_id is None and row.fence is None
                    and row.world_snapshot_id is None and row.player_snapshot_id is None)
            elif kind is ArtifactHolderKind.SNAPSHOT:
                valid = (row.operation_id is None and row.fence is None and row.retained_artifact_id is None
                    and ((row.world_snapshot_id is None) != (row.player_snapshot_id is None)))
            else:
                valid = row.pin_id is not None and all(value is None for value in (row.operation_id, row.fence,
                    row.retained_artifact_id, row.world_snapshot_id, row.player_snapshot_id))
            valid = valid and ((row.pin_id is not None) == (kind is ArtifactHolderKind.PIN))
            key = SqliteArtifactHolders._key(row)
            previous = latest.get(key)
            if (not valid or row.artifact_id != artifact_id or row.event_kind not in ("acquire", "release")
                    or row.event_seq != (1 if previous is None else previous.event_seq + 1)
                    or row.predecessor_id != (None if previous is None else previous.event_id)
                    or (previous is None and row.event_kind != "acquire")
                    or (previous is not None and row.event_kind == previous.event_kind)
                    or (kind in (ArtifactHolderKind.SNAPSHOT, ArtifactHolderKind.PIN) and row.event_kind == "release")):
                raise PublicationInfrastructureError("invalid artifact holder chain")
            latest[key] = row
        return tuple(latest.values())

    @staticmethod
    async def _append(access: ScopedSqliteAccess, scope: CommitScope,
                      template: ArtifactHolderEventRow, acquire: bool) -> None:
        latest = await SqliteArtifactHolders._chain(access, scope, template.artifact_id)
        previous = next((row for row in latest if SqliteArtifactHolders._key(row) == SqliteArtifactHolders._key(template)), None)
        event_kind = "acquire" if acquire else "release"
        if previous is None and not acquire:
            return
        if previous is not None and previous.event_kind == event_kind:
            return
        await access.insert(scope, replace(template, event_id=runtime_uid(),
            predecessor_id=None if previous is None else previous.event_id,
            event_seq=1 if previous is None else previous.event_seq + 1, event_kind=event_kind))

    @staticmethod
    async def _operation_hold(access: ScopedSqliteAccess, scope: CommitScope,
                              artifact_id: EntityUid, lease: OperationLeaseRef) -> None:
        """Atomic reserve delegates its holder append here, without a second UOW."""
        await SqliteArtifactHolders._append(access, scope, ArtifactHolderEventRow(runtime_uid(), artifact_id,
            ArtifactHolderKind.OPERATION.value, lease.operation_id, lease.fence, None, None, None, None, 1, "acquire"), True)

    async def _hydrate(self, scope: CommitReadScope | CommitScope, row: ArtifactHolderEventRow) -> ArtifactHolderRef:
        if row.holder_kind == ArtifactHolderKind.OPERATION.value:
            if row.operation_id is None:
                raise PublicationInfrastructureError("missing operation holder owner")
            try:
                record = await self._operations._load(row.operation_id, scope)
            except (ValueError, TypeError) as error:
                raise PublicationInfrastructureError("invalid persisted holder operation") from error
            if record is None or row.fence is None or row.fence > record.fence:
                raise PublicationInfrastructureError("missing operation holder owner or invalid historical fence")
            return OperationHolder(lease=OperationLeaseRef(operation_id=record.operation_id, world_uid=record.world_uid,
                kind=record.kind, preparation_fingerprint=record.preparation_fingerprint, fence=row.fence))
        if row.holder_kind == ArtifactHolderKind.ARTIFACT.value:
            if row.retained_artifact_id is None:
                raise PublicationInfrastructureError("missing retention owner")
            return ArtifactRetentionHolder(artifact=await self._catalog._by_id(scope, row.retained_artifact_id))
        if row.pin_id is not None:
            return PinHolder(pin_id=row.pin_id)
        snapshot_id = row.world_snapshot_id if row.world_snapshot_id is not None else row.player_snapshot_id
        if snapshot_id is None:
            raise PublicationInfrastructureError("missing snapshot holder owner")
        ref = await self._history.resolve_ref(snapshot_id,
            SnapshotChainKind.WORLD if row.world_snapshot_id is not None else SnapshotChainKind.PLAYER,
            scope=scope.read_scope if isinstance(scope, CommitScope) else scope)
        if ref is None:
            raise PublicationInfrastructureError("missing snapshot holder owner")
        return SnapshotHolder(snapshot=ref)

    async def _template(self, scope: CommitReadScope | CommitScope,
                        artifact_id: EntityUid, holder: ArtifactHolderRef) -> ArtifactHolderEventRow:
        op, fence, retained, world, player = None, None, None, None, None
        if isinstance(holder, OperationHolder):
            op, fence = holder.lease.operation_id, holder.lease.fence
        elif isinstance(holder, ArtifactRetentionHolder):
            owner = await self._catalog._find(scope, holder.artifact)
            if owner is None:
                raise ValueError("unknown retention owner")
            retained = owner.artifact_id
        elif isinstance(holder, PinHolder):
            return ArtifactHolderEventRow(runtime_uid(), artifact_id, holder.kind.value, None, None, None,
                None, None, None, 1, "acquire", holder.pin_id)
        elif isinstance(holder.snapshot, WorldSnapshotRef):
            world = holder.snapshot.snapshot_id
        else:
            player = holder.snapshot.snapshot_id
        return ArtifactHolderEventRow(runtime_uid(), artifact_id, holder.kind.value, op, fence,
            retained, world, player, None, 1, "acquire")

    async def _current(self, scope: CommitReadScope | CommitScope, lease: OperationLeaseRef) -> None:
        try:
            record = await self._operations._load(lease.operation_id, scope)
        except (ValueError, TypeError) as error:
            raise PublicationInfrastructureError("invalid persisted holder operation") from error
        if record is None or OperationLeaseRef(operation_id=record.operation_id, world_uid=record.world_uid,
                kind=record.kind, preparation_fingerprint=record.preparation_fingerprint, fence=record.fence) != lease:
            raise ValueError("missing or stale operation holder lease")

    async def _holders(self, scope: CommitReadScope | CommitScope, ref: ArtifactRef) -> tuple[ArtifactHolderRef, ...]:
        artifact = await self._catalog._find(scope, ref)
        if artifact is None:
            return ()
        rows = await self._chain(self._access, scope, artifact.artifact_id)
        result = []
        for row in rows:
            holder = await self._hydrate(scope, row)
            if row.event_kind == "acquire":
                result.append(holder)
        return tuple(result)

    async def holders(self, ref: ArtifactRef) -> tuple[ArtifactHolderRef, ...]:
        ref = ArtifactRef.model_validate(ref, strict=True)
        async with self._scopes.read_scope() as scope:
            return await self._holders(scope, ref)

    async def is_held(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> bool:
        holder = TypeAdapter(ArtifactHolderRef).validate_python(holder, strict=True)
        return holder in await self.holders(ref)

    async def acquire(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> None:
        ref = ArtifactRef.model_validate(ref, strict=True)
        holder = TypeAdapter(ArtifactHolderRef).validate_python(holder, strict=True)
        async with self._scopes.transaction(holder.lease.operation_id if isinstance(holder, OperationHolder) else runtime_uid()) as scope:
            artifact = await self._catalog._find(scope, ref)
            if artifact is None:
                raise ValueError("unknown held artifact")
            if isinstance(holder, OperationHolder):
                await self._current(scope, holder.lease)
                record = await self._operations._load(holder.lease.operation_id, scope)
                if record is None or record.phase is OperationPhase.TERMINAL:
                    raise ValueError("closed operation holder")
            else:
                if not await self._catalog.is_sealed(ref):
                    raise ValueError("published/retention hold requires sealed content")
                if isinstance(holder, ArtifactRetentionHolder):
                    if not await self._catalog.is_sealed(holder.artifact):
                        raise ValueError("retention owner must be sealed")
                elif isinstance(holder, SnapshotHolder):
                    actual = await self._history.resolve_ref(holder.snapshot.snapshot_id, holder.snapshot.kind, scope=scope.read_scope)
                    if actual != holder.snapshot:
                        raise ValueError("snapshot holder identity mismatch")
            await self._append(self._access, scope, await self._template(scope, artifact.artifact_id, holder), True)

    async def release(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> None:
        ref = ArtifactRef.model_validate(ref, strict=True)
        holder = TypeAdapter(ArtifactHolderRef).validate_python(holder, strict=True)
        if isinstance(holder, (SnapshotHolder, PinHolder)):
            raise ValueError("published history holds cannot be released")
        async with self._scopes.transaction(holder.lease.operation_id if isinstance(holder, OperationHolder) else runtime_uid()) as scope:
            artifact = await self._catalog._find(scope, ref)
            if artifact is None:
                raise ValueError("unknown held artifact")
            if isinstance(holder, OperationHolder):
                await self._catalog._lease(scope, holder.lease, writable=False)
                if any(c.fence == holder.lease.fence for c in await self._catalog._writers(scope, operation_id=holder.lease.operation_id)):
                    raise ValueError("operation writers must drain before release")
            await self._append(self._access, scope, await self._template(scope, artifact.artifact_id, holder), False)

    async def handoff(self, scope: CommitScope, lease: OperationLeaseRef,
                      snapshots: tuple[SnapshotRef, ...], retained_refs: tuple[ArtifactRef, ...]) -> None:
        lease = OperationLeaseRef.model_validate(lease, strict=True)
        snapshots = TypeAdapter(tuple[SnapshotRef, ...]).validate_python(snapshots, strict=True)
        retained_refs = TypeAdapter(tuple[ArtifactRef, ...]).validate_python(retained_refs, strict=True)
        if len(set(snapshots)) != len(snapshots) or len(set(retained_refs)) != len(retained_refs):
            raise ValueError("duplicate handoff refs")
        async with self._scopes.bind(scope):
            if self._scopes.commits.registry.operation_id(scope) != lease.operation_id:
                raise ValueError("handoff scope operation mismatch")
            await self._catalog._lease(scope, lease, writable=False)
            record = await self._operations._load(lease.operation_id, scope)
            if record is None or record.phase is not OperationPhase.APPLYING:
                raise ValueError("handoff requires a claimed publication operation")
            if await self._catalog._writers(scope, operation_id=lease.operation_id):
                raise ValueError("handoff requires drained writers")
            planned: dict[ArtifactRef, list[SnapshotHolder]] = {}
            for snapshot in snapshots:
                metadata = await self._history.read(snapshot, scope=scope.read_scope)
                if metadata is None or metadata.operation_id != lease.operation_id:
                    raise ValueError("handoff snapshot is not owned by operation")
                if isinstance(snapshot, WorldSnapshotRef) and snapshot.world_uid != lease.world_uid:
                    raise ValueError("handoff snapshot world mismatch")
                for ref in metadata.retained_artifacts:
                    planned.setdefault(ref, []).append(SnapshotHolder(snapshot=snapshot))
            # The caller may catch a refusal and commit the borrowed scope.
            # Validate every destination, including metadata-only refs, before
            # the first append; acquire must not discover a late corrupt chain.
            operation_holder = OperationHolder(lease=lease)
            checked_holders: dict[ArtifactRef, tuple[ArtifactHolderRef, ...]] = {}
            for ref in dict.fromkeys((*planned, *retained_refs)):
                if not await self._catalog.is_sealed(ref):
                    raise ValueError("handoff requires sealed refs")
                checked_holders[ref] = await self._holders(scope, ref)
            for ref in retained_refs:
                held = checked_holders[ref]
                retention = [h for h in held if isinstance(h, ArtifactRetentionHolder)]
                for h in retention:
                    if not await self._catalog.is_sealed(h.artifact):
                        raise ValueError("retention owner must be sealed")
                if not planned.get(ref) and not retention:
                    raise ValueError("transferred ref has no published/retention owner")
                if operation_holder not in held:
                    artifact = await self._catalog._find(scope, ref)
                    rows = () if artifact is None else await self._chain(self._access, scope, artifact.artifact_id)
                    released = any(h.operation_id == lease.operation_id and h.fence == lease.fence
                        and h.event_kind == "release" for h in rows)
                    if not released or not (retention or any(h in held for h in planned.get(ref, []))):
                        raise ValueError("missing operation hold or previous handoff")
            for ref, snapshot_holders in planned.items():
                for holder in snapshot_holders:
                    await self.acquire(ref, holder)
            for ref in retained_refs:
                await self.release(ref, operation_holder)
