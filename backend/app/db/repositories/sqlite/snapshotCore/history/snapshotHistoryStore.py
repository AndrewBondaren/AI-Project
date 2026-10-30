"""Immutable metadata envelopes only; no domain payload reads, materialization or commit."""

from pydantic import TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec
from app.application.worldSnapshot.validation.receiptProvenance import validate_receipt_provenance
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import (
    SnapshotEnvelope, WorldSnapshotMetadata, PlayerSnapshotMetadata,
)
from app.db.models.snapshotCore.historyRows import WorldSnapshotRow, PlayerSnapshotRow
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _fields, _wire
from app.db.repositories.sqlite.snapshotCore.history.rowProjection import encode_history_row, decode_history_row


class SqliteSnapshotHistoryStore:
    def __init__(self, commits: SqlitePublicationCommitStore, access: ScopedSqliteAccess, codec: SnapshotEnvelopeCodec | None = None) -> None:
        if access.registry is not commits.registry:
            raise ValueError("adapter/access must share the coordinator's registry")
        self._access, self._registry = access, access.registry
        self._commits = commits
        self._codec = codec if codec is not None else SnapshotEnvelopeCodec()

    async def _validate_parent(self, ref: SnapshotRef | None, scope: CommitReadScope) -> None:
        if ref is None:
            return
        if isinstance(ref, WorldSnapshotRef):
            parent = await self._access.one(scope,
                "SELECT snapshot_id, world_uid, timeline_id FROM world_snapshots WHERE snapshot_id=?", (ref.snapshot_id,))
            if parent is None:
                raise PublicationInfrastructureError("missing world snapshot parent")
            _fields(parent, uids=("snapshot_id", "world_uid", "timeline_id"))
            actual = WorldSnapshotRef(world_uid=parent["world_uid"], timeline_id=parent["timeline_id"], snapshot_id=parent["snapshot_id"])
        else:
            parent = await self._access.one(scope,
                "SELECT player_snapshot_id, player_uid FROM player_snapshots WHERE player_snapshot_id=?", (ref.snapshot_id,))
            if parent is None:
                raise PublicationInfrastructureError("missing player snapshot parent")
            _fields(parent, uids=("player_snapshot_id", "player_uid"))
            actual = PlayerSnapshotRef(player_uid=parent["player_uid"], snapshot_id=parent["player_snapshot_id"])
        if actual != ref:
            raise PublicationInfrastructureError("snapshot parent ref disagrees with storage")

    async def _world_for_player(self, operation_id: EntityUid, scope: CommitReadScope) -> WorldSnapshotMetadata:
        row = await self._access.one(scope, "SELECT * FROM world_snapshots WHERE operation_id=?", (operation_id,))
        if row is None:
            raise PublicationInfrastructureError("player snapshot requires its world snapshot")
        _fields(row, uids=("snapshot_id", "world_uid", "timeline_id", "operation_id"))
        ref = WorldSnapshotRef(world_uid=row["world_uid"], timeline_id=row["timeline_id"], snapshot_id=row["snapshot_id"])
        metadata = await self.read(ref, scope=scope)
        if not isinstance(metadata, WorldSnapshotMetadata):
            raise PublicationInfrastructureError("player snapshot requires its world metadata")
        return metadata

    async def append(self, scope: CommitScope, metadata: SnapshotEnvelope, receipts: tuple[SectionApplyReceipt, ...]) -> None:
        operation_id = self._registry.operation_id(scope)
        metadata = TypeAdapter(SnapshotEnvelope).validate_python(metadata, strict=True)
        receipts = TypeAdapter(tuple[SectionApplyReceipt, ...]).validate_python(receipts, strict=True)
        await self._validate_parent(metadata.parent, scope.read_scope)
        base = None if metadata.parent is None else await self.read(metadata.parent, scope=scope.read_scope)
        validate_receipt_provenance(metadata, receipts, base, operation_id)
        world = await self._world_for_player(operation_id, scope.read_scope) if isinstance(metadata, PlayerSnapshotMetadata) else None
        row = encode_history_row(metadata, world, self._codec)
        await self._access.insert(scope, row)

    async def read(self, ref: SnapshotRef, *, scope: CommitReadScope | None = None) -> SnapshotEnvelope | None:
        ref = TypeAdapter(SnapshotRef).validate_python(ref, strict=True)
        world_ref = isinstance(ref, WorldSnapshotRef)
        model = WorldSnapshotRow if world_ref else PlayerSnapshotRow
        async with self._commits.read_scope(scope) as pinned:
            row = await self._access.one(pinned, f"SELECT * FROM {model.__table__} WHERE {model.__pk__}=?", (ref.snapshot_id,))
            if row is None:
                return None
            metadata = decode_history_row(row, ref, self._codec)
            operation = await self._access.one(pinned, "SELECT * FROM publication_operations WHERE operation_id=?", (row["operation_id"],))
            if operation is None:
                raise PublicationInfrastructureError("missing snapshot operation")
            _fields(operation, uids=("operation_id", "world_uid"), hashes=("preparation_fingerprint",))
            if operation["world_uid"] != row["world_uid"] or _wire(OperationKind, operation["kind"]) is not OperationKind.SNAPSHOT_APPLY:
                raise PublicationInfrastructureError("snapshot operation owner/kind mismatch")
            if isinstance(metadata, PlayerSnapshotMetadata):
                owner = await self._access.one(pinned, "SELECT character_uid, world_uid FROM character_sheet WHERE character_uid=?", (row["player_uid"],))
                if owner is None:
                    raise PublicationInfrastructureError("missing player owner")
                _fields(owner, uids=("character_uid", "world_uid"))
                if owner["world_uid"] != row["world_uid"]:
                    raise PublicationInfrastructureError("player snapshot belongs to another world")
                world = await self._world_for_player(row["operation_id"], pinned)
                if (row["world_uid"] != world.ref.world_uid
                        or row["timeline_id"] != world.ref.timeline_id or row["turn_id"] != world.turn_id):
                    raise PublicationInfrastructureError("player/world operation mismatch")
                if row["session_id"] is not None:
                    session = await self._access.one(pinned, "SELECT id, world_uid, player_character_id FROM game_sessions WHERE id=?", (row["session_id"],))
                    if session is None:
                        raise PublicationInfrastructureError("missing session audit")
                    _fields(session, uids=("id", "world_uid", "player_character_id"))
                    if session["world_uid"] != row["world_uid"] or session["player_character_id"] != metadata.ref.player_uid:
                        raise PublicationInfrastructureError("session audit owner mismatch")
            await self._validate_parent(metadata.parent, pinned)
            return metadata
