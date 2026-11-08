"""Append-only world publication CAS/explicit bootstrap, under the shared commit owner."""

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.results.publication import (
    CasDecision, ObservedPublication, WorldCasMismatch, WorldCasResult,
)
from app.db.models.snapshotCore.publicationRows import WorldPublicationRow
from app.db.models.snapshotCore.operationRows import PublicationOperationRow
from .worldPublicationValidation import decode_publication, validate_bootstrap, validate_transition
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _UID, _fields
from app.ids.deterministicIds import runtime_uid


class SqliteWorldPublicationStore:
    def __init__(self, commits: SqlitePublicationCommitStore, access: ScopedSqliteAccess) -> None:
        if access.registry is not commits.registry:
            raise ValueError("adapter/access must share the coordinator's registry")
        self._access, self._registry = access, access.registry
        self._commits = commits

    async def _ref(self, row: WorldPublicationRow | None, scope) -> WorldPublicationRef:
        if row is None:
            raise PublicationInfrastructureError("world publication is missing; read does not initialize it")
        if row.predecessor_id is None:
            validate_bootstrap(row)
        else:
            parent = await self._publication_by_id(row.predecessor_id, scope)
            if parent is None:
                raise PublicationInfrastructureError("missing publication predecessor")
            operation = await self._access.one_row(scope, PublicationOperationRow,
                "SELECT * FROM publication_operations WHERE operation_id=?", (row.operation_id,))
            if operation is None:
                raise PublicationInfrastructureError("publication operation is missing")
            validate_transition(parent, row, operation)
        await self._check_timeline(row, scope)
        head = await self._read_head(row, scope)
        return WorldPublicationRef(world_uid=row.world_uid, publication_id=row.publication_id,
            pack_hash=row.pack_hash, snapshot_head=head, active_timeline_id=row.active_timeline_id,
            gameplay_started=row.gameplay_started)

    async def _check_timeline(self, row: WorldPublicationRow, scope) -> None:
        if row.active_timeline_id is not None:
            timeline = await self._access.one(scope, "SELECT timeline_id, world_uid FROM timelines WHERE timeline_id=?", (row.active_timeline_id,))
            if timeline is None:
                raise PublicationInfrastructureError("missing active timeline")
            _fields(timeline, uids=("timeline_id", "world_uid"))
            if timeline["world_uid"] != row.world_uid:
                raise PublicationInfrastructureError("active timeline belongs to another world")

    async def _read_head(self, row: WorldPublicationRow, scope) -> WorldSnapshotRef | None:
        if row.snapshot_head_id is None:
            return None
        stored = await self._access.one(scope,
            "SELECT snapshot_id, world_uid, timeline_id, operation_id FROM world_snapshots WHERE snapshot_id=?",
            (row.snapshot_head_id,))
        if stored is None:
            raise PublicationInfrastructureError("missing world snapshot head")
        _fields(stored, uids=("snapshot_id", "world_uid", "timeline_id", "operation_id"))
        head = WorldSnapshotRef(world_uid=stored["world_uid"], timeline_id=stored["timeline_id"], snapshot_id=stored["snapshot_id"])
        if stored["operation_id"] != row.operation_id:
            raise PublicationInfrastructureError("world head/operation mismatch")
        # SNAPSHOT_APPLY is the only supported transition that persists a head.
        if head.world_uid != row.world_uid or head.timeline_id != row.active_timeline_id:
            raise PublicationInfrastructureError("world head owner/timeline mismatch")
        return head

    async def _latest(self, world_uid, scope):
        raw = await self._access.one(scope,
            "SELECT * FROM world_publications WHERE world_uid=? ORDER BY publication_seq DESC LIMIT 1", (world_uid,))
        return None if raw is None else decode_publication(raw)

    async def _publication_by_id(self, publication_id, scope) -> WorldPublicationRow | None:
        raw = await self._access.one(scope,
            "SELECT * FROM world_publications WHERE publication_id=?", (publication_id,))
        return None if raw is None else decode_publication(raw)

    async def _by_id(self, publication_id, scope):
        publication_id = _UID.validate_python(publication_id, strict=True)
        return await self._ref(await self._publication_by_id(publication_id, scope), scope)

    async def read_exact(self, world_uid: EntityUid, publication_id: EntityUid, *,
                         scope: CommitReadScope) -> WorldPublicationRef | None:
        self._registry.check(scope)
        world_uid = _UID.validate_python(world_uid, strict=True)
        publication_id = _UID.validate_python(publication_id, strict=True)
        row = await self._access.one(scope,
            "SELECT * FROM world_publications WHERE world_uid=? AND publication_id=?", (world_uid, publication_id))
        return None if row is None else await self._ref(decode_publication(row), scope)

    async def read(self, world_uid: EntityUid, *, scope: CommitReadScope | None = None) -> WorldPublicationRef:
        world_uid = _UID.validate_python(world_uid, strict=True)
        async with self._commits.read_scope(scope) as pinned:
            return await self._ref(await self._latest(world_uid, pinned), pinned)

    async def read_current_if_world_exists(self, world_uid: EntityUid, scope: CommitReadScope) -> WorldPublicationRef | None:
        world = await self._access.one(scope, "SELECT world_uid FROM worlds WHERE world_uid=?", (world_uid,))
        if world is None:
            return None
        return await self._ref(await self._latest(world_uid, scope), scope)

    async def initialize(self, scope: CommitScope, world_uid: EntityUid) -> WorldPublicationRef:
        self._registry.check(scope, True)
        world_uid = _UID.validate_python(world_uid, strict=True)
        stored = await self._latest(world_uid, scope)
        if stored is not None:
            return await self._ref(stored, scope)
        publication_id = _UID.validate_python(runtime_uid(), strict=True)
        initial = WorldPublicationRow(
            publication_id=publication_id, world_uid=world_uid, predecessor_id=None, publication_seq=1,
            operation_id=None, pack_hash=None, snapshot_head_id=None, active_timeline_id=None, gameplay_started=False,
        )
        await self._access.insert(scope, initial)
        return await self._ref(initial, scope)

    async def compare_append(self, scope: CommitScope, expected: WorldPublicationRef, next_publication: WorldPublicationRef) -> WorldCasResult:
        operation_id = self._registry.operation_id(scope)
        expected = WorldPublicationRef.model_validate(expected, strict=True)
        next_publication = WorldPublicationRef.model_validate(next_publication, strict=True)
        if expected.world_uid != next_publication.world_uid:
            raise ValueError("next publication belongs to another world")
        stored = await self._latest(expected.world_uid, scope)
        if stored is None:
            raise PublicationInfrastructureError("world publication is not initialized")
        observed = await self._ref(stored, scope)
        if observed != expected:
            differing = tuple(name for name in WorldPublicationRef.model_fields
                              if getattr(expected, name) != getattr(observed, name))
            return WorldCasMismatch(operation_id, expected, observed,
                ObservedPublication(stored.publication_id, stored.operation_id), differing)
        head = next_publication.snapshot_head
        await self._access.insert(scope, WorldPublicationRow(
            publication_id=next_publication.publication_id, world_uid=expected.world_uid,
            predecessor_id=expected.publication_id, publication_seq=stored.publication_seq + 1,
            operation_id=operation_id, pack_hash=next_publication.pack_hash,
            snapshot_head_id=head.snapshot_id if head is not None else None,
            active_timeline_id=next_publication.active_timeline_id, gameplay_started=next_publication.gameplay_started,
        ))
        return CasDecision.APPLIED
