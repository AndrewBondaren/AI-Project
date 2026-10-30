"""Append-only world publication CAS/explicit bootstrap, under the shared commit owner."""

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.results.publication import CasDecision
from app.db.models.snapshotCore.publicationRows import WorldPublicationRow
from app.db.repositories.sqlite.snapshotCore.commitScope import (
    SqlitePublicationCommitStore, _UID, _fields, _insert, _one, _read_scope, _wire, _write_operation,
)
from app.ids.deterministicIds import runtime_uid


class SqliteWorldPublicationStore:
    def __init__(self, commits: SqlitePublicationCommitStore) -> None:
        self._commits = commits

    async def _ref(self, row, scope) -> WorldPublicationRef:
        if row is None:
            raise PublicationInfrastructureError("world publication is missing; read does not initialize it")
        _fields(row, uids=("publication_id", "world_uid"),
                optional_uids=("predecessor_id", "operation_id", "snapshot_head_id", "active_timeline_id"),
                positives=("publication_seq",), optional_hashes=("pack_hash",), booleans=("gameplay_started",))
        if row["predecessor_id"] is None:
            if row["publication_seq"] != 1 or any(row[name] is not None for name in (
                    "operation_id", "pack_hash", "snapshot_head_id", "active_timeline_id")) or row["gameplay_started"]:
                raise PublicationInfrastructureError("invalid bootstrap publication")
        else:
            parent = await _one(self._commits, scope, "SELECT * FROM world_publications WHERE publication_id=?", (row["predecessor_id"],))
            if parent is None:
                raise PublicationInfrastructureError("missing publication predecessor")
            _fields(parent, uids=("publication_id", "world_uid"), positives=("publication_seq",),
                    optional_hashes=("pack_hash",), booleans=("gameplay_started",))
            if parent["world_uid"] != row["world_uid"] or row["publication_seq"] != parent["publication_seq"] + 1:
                raise PublicationInfrastructureError("publication chain owner/sequence mismatch")
            operation = await _one(self._commits, scope, "SELECT * FROM publication_operations WHERE operation_id=?", (row["operation_id"],))
            if operation is None:
                raise PublicationInfrastructureError("publication operation is missing")
            _fields(operation, uids=("operation_id", "world_uid"), hashes=("preparation_fingerprint",))
            kind = _wire(OperationKind, operation["kind"])
            if operation["world_uid"] != row["world_uid"]:
                raise PublicationInfrastructureError("publication operation belongs to another world")
            if parent["gameplay_started"]:
                if (not row["gameplay_started"] or row["pack_hash"] != parent["pack_hash"]
                        or row["active_timeline_id"] != parent["active_timeline_id"] or kind is not OperationKind.SNAPSHOT_APPLY):
                    raise PublicationInfrastructureError("invalid runtime publication transition")
            elif row["gameplay_started"]:
                if kind is not OperationKind.GAMEPLAY_START or row["pack_hash"] != parent["pack_hash"] or row["snapshot_head_id"] is not None:
                    raise PublicationInfrastructureError("invalid gameplay start publication")
            elif kind is not OperationKind.PACK_ACTIVATION or row["pack_hash"] is None:
                raise PublicationInfrastructureError("invalid pregame pack publication")
        head = None
        if row["snapshot_head_id"] is not None:
            stored = await _one(self._commits, scope,
                "SELECT snapshot_id, world_uid, timeline_id, operation_id FROM world_snapshots WHERE snapshot_id=?",
                (row["snapshot_head_id"],))
            if stored is None:
                raise PublicationInfrastructureError("missing world snapshot head")
            _fields(stored, uids=("snapshot_id", "world_uid", "timeline_id", "operation_id"))
            head = WorldSnapshotRef(world_uid=stored["world_uid"], timeline_id=stored["timeline_id"], snapshot_id=stored["snapshot_id"])
            if stored["operation_id"] != row["operation_id"]:
                raise PublicationInfrastructureError("world head/operation mismatch")
        return WorldPublicationRef(world_uid=row["world_uid"], publication_id=row["publication_id"],
            pack_hash=row["pack_hash"], snapshot_head=head, active_timeline_id=row["active_timeline_id"],
            gameplay_started=bool(row["gameplay_started"]))

    async def _latest(self, world_uid, scope):
        return await _one(self._commits, scope,
            "SELECT * FROM world_publications WHERE world_uid=? ORDER BY publication_seq DESC LIMIT 1", (world_uid,))

    async def _by_id(self, publication_id, scope):
        publication_id = _UID.validate_python(publication_id, strict=True)
        return await self._ref(await _one(self._commits, scope,
            "SELECT * FROM world_publications WHERE publication_id=?", (publication_id,)), scope)

    async def read(self, world_uid: EntityUid, *, scope: CommitReadScope | None = None) -> WorldPublicationRef:
        world_uid = _UID.validate_python(world_uid, strict=True)
        async with _read_scope(self._commits, scope) as pinned:
            return await self._ref(await self._latest(world_uid, pinned), pinned)

    async def initialize(self, scope: CommitScope, world_uid: EntityUid) -> WorldPublicationRef:
        self._commits._check(scope, True)
        world_uid = _UID.validate_python(world_uid, strict=True)
        stored = await self._latest(world_uid, scope)
        if stored is not None:
            return await self._ref(stored, scope)
        publication_id = _UID.validate_python(runtime_uid(), strict=True)
        await _insert(self._commits, scope, WorldPublicationRow(publication_id, world_uid, None, 1,
                      None, None, None, None, False))
        return WorldPublicationRef(world_uid=world_uid, publication_id=publication_id, pack_hash=None,
                                   snapshot_head=None, active_timeline_id=None, gameplay_started=False)

    async def compare_append(self, scope: CommitScope, expected: WorldPublicationRef, next_publication: WorldPublicationRef) -> CasDecision:
        operation_id = _write_operation(self._commits, scope)
        expected = WorldPublicationRef.model_validate(expected, strict=True)
        next_publication = WorldPublicationRef.model_validate(next_publication, strict=True)
        if expected.world_uid != next_publication.world_uid:
            raise ValueError("next publication belongs to another world")
        stored = await self._latest(expected.world_uid, scope)
        if stored is None:
            raise PublicationInfrastructureError("world publication is not initialized")
        if await self._ref(stored, scope) != expected:
            return CasDecision.MISMATCH
        await _insert(self._commits, scope, WorldPublicationRow(next_publication.publication_id, expected.world_uid,
            expected.publication_id, stored["publication_seq"] + 1, operation_id, next_publication.pack_hash,
            None if next_publication.snapshot_head is None else next_publication.snapshot_head.snapshot_id,
            next_publication.active_timeline_id, next_publication.gameplay_started))
        return CasDecision.APPLIED
