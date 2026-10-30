"""Immutable metadata envelopes only; no domain payload reads, materialization or commit."""

from pydantic import TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec
from app.application.encoding.canonicalCodec import content_digest
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.patch.values import FormatVersion
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import (
    SnapshotEnvelope, WorldSnapshotMetadata, PlayerSnapshotMetadata, CreatedAtUtc,
)
from app.db.models.snapshotCore.historyRows import WorldSnapshotRow, PlayerSnapshotRow
from app.db.repositories.sqlite.snapshotCore.commitScope import (
    SqlitePublicationCommitStore, _checked_blob, _fields, _insert, _one, _read_scope, _write_operation,
)


class SqliteSnapshotHistoryStore:
    def __init__(self, commits: SqlitePublicationCommitStore, codec: SnapshotEnvelopeCodec | None = None) -> None:
        self._commits = commits
        self._codec = codec if codec is not None else SnapshotEnvelopeCodec()

    async def _validate_parent(self, ref, scope):
        if ref is None:
            return
        if isinstance(ref, WorldSnapshotRef):
            parent = await _one(self._commits, scope,
                "SELECT snapshot_id, world_uid, timeline_id FROM world_snapshots WHERE snapshot_id=?", (ref.snapshot_id,))
            if parent is None:
                raise PublicationInfrastructureError("missing world snapshot parent")
            _fields(parent, uids=("snapshot_id", "world_uid", "timeline_id"))
            actual = WorldSnapshotRef(world_uid=parent["world_uid"], timeline_id=parent["timeline_id"], snapshot_id=parent["snapshot_id"])
        else:
            parent = await _one(self._commits, scope,
                "SELECT player_snapshot_id, player_uid FROM player_snapshots WHERE player_snapshot_id=?", (ref.snapshot_id,))
            if parent is None:
                raise PublicationInfrastructureError("missing player snapshot parent")
            _fields(parent, uids=("player_snapshot_id", "player_uid"))
            actual = PlayerSnapshotRef(player_uid=parent["player_uid"], snapshot_id=parent["player_snapshot_id"])
        if actual != ref:
            raise PublicationInfrastructureError("snapshot parent ref disagrees with storage")

    async def _world_for_player(self, operation_id, scope):
        row = await _one(self._commits, scope, "SELECT * FROM world_snapshots WHERE operation_id=?", (operation_id,))
        if row is None:
            raise PublicationInfrastructureError("player snapshot requires its world snapshot")
        _fields(row, uids=("snapshot_id", "world_uid", "timeline_id", "operation_id"))
        ref = WorldSnapshotRef(world_uid=row["world_uid"], timeline_id=row["timeline_id"], snapshot_id=row["snapshot_id"])
        return await self.read(ref, scope=scope.read_scope)

    async def append(self, scope: CommitScope, metadata: SnapshotEnvelope, receipts: tuple[SectionApplyReceipt, ...]) -> None:
        operation_id = _write_operation(self._commits, scope)
        metadata = TypeAdapter(SnapshotEnvelope).validate_python(metadata, strict=True)
        receipts = TypeAdapter(tuple[SectionApplyReceipt, ...]).validate_python(receipts, strict=True)
        if metadata.operation_id != operation_id:
            raise ValueError("metadata belongs to another publication operation")
        if any(patch.operation_id != operation_id for receipt in receipts for patch in receipt.changed):
            raise ValueError("receipt belongs to another operation")
        history = tuple(ref for receipt in receipts for ref in receipt.history_refs if ref.snapshot == metadata.ref)
        if set(history) != set(metadata.history_refs):
            raise ValueError("metadata history does not match section receipts")
        for receipt in receipts:
            for ref in receipt.state_refs:
                same_owner = ((isinstance(ref.snapshot, WorldSnapshotRef) and isinstance(metadata.ref, WorldSnapshotRef)
                               and ref.snapshot.world_uid == metadata.ref.world_uid) or
                              (isinstance(ref.snapshot, PlayerSnapshotRef) and isinstance(metadata.ref, PlayerSnapshotRef)
                               and ref.snapshot.player_uid == metadata.ref.player_uid))
                if same_owner and ref not in metadata.state_refs:
                    raise ValueError("receipt state is missing from the resulting metadata")
        await self._validate_parent(metadata.parent, scope)
        base = None if metadata.parent is None else await self.read(metadata.parent, scope=scope.read_scope)
        if any(ref.snapshot != metadata.ref and (base is None or ref not in base.state_refs) for ref in metadata.state_refs):
            raise ValueError("retained section state is not reachable from the pinned base")
        data = self._codec.encode(metadata)
        checksum = content_digest(data).hex()
        if isinstance(metadata, WorldSnapshotMetadata):
            row = WorldSnapshotRow(metadata.ref.snapshot_id, metadata.ref.timeline_id, metadata.ref.world_uid,
                metadata.turn_id, metadata.created_at, None if metadata.parent is None else metadata.parent.snapshot_id,
                data, checksum, operation_id, metadata.envelope_format_version, metadata.base_pack_hash)
        else:
            if not isinstance(metadata.ref, PlayerSnapshotRef):
                raise ValueError("player metadata requires a player ref")
            world = await self._world_for_player(operation_id, scope)
            if not isinstance(world, WorldSnapshotMetadata) or world.turn_id != metadata.turn_id:
                raise ValueError("player tick does not match world tick")
            row = PlayerSnapshotRow(metadata.ref.snapshot_id, metadata.ref.player_uid, world.ref.world_uid,
                world.ref.timeline_id, None, metadata.turn_id, metadata.created_at,
                None if metadata.parent is None else metadata.parent.snapshot_id, operation_id,
                metadata.envelope_format_version, data, checksum)
        await _insert(self._commits, scope, row)

    async def read(self, ref: SnapshotRef, *, scope: CommitReadScope | None = None) -> SnapshotEnvelope | None:
        ref = TypeAdapter(SnapshotRef).validate_python(ref, strict=True)
        world_ref = isinstance(ref, WorldSnapshotRef)
        model = WorldSnapshotRow if world_ref else PlayerSnapshotRow
        async with _read_scope(self._commits, scope) as pinned:
            row = await _one(self._commits, pinned, f"SELECT * FROM {model.__table__} WHERE {model.__pk__}=?", (ref.snapshot_id,))
            if row is None:
                return None
            _fields(row, uids=(("snapshot_id", "world_uid", "timeline_id", "operation_id") if world_ref else
                    ("player_snapshot_id", "player_uid", "world_uid", "timeline_id", "operation_id")),
                optional_uids=(("parent_snapshot_id",) if world_ref else ("parent_player_snapshot_id", "session_id")),
                positives=("turn_id", "envelope_format_version"),
                hashes=(("snapshot_checksum", "base_pack_hash") if world_ref else ("snapshot_checksum",)))
            TypeAdapter(CreatedAtUtc).validate_python(row["created_at"], strict=True)
            TypeAdapter(FormatVersion).validate_python(row["envelope_format_version"], strict=True)
            metadata = self._codec.decode(_checked_blob(row["snapshot_data"], row["snapshot_checksum"]))
            if (metadata.ref != ref or (world_ref and not isinstance(metadata, WorldSnapshotMetadata))
                    or (not world_ref and not isinstance(metadata, PlayerSnapshotMetadata))):
                raise PublicationInfrastructureError("snapshot chain/ref does not match its envelope")
            parent_id = row["parent_snapshot_id"] if world_ref else row["parent_player_snapshot_id"]
            if (metadata.operation_id != row["operation_id"] or metadata.turn_id != row["turn_id"]
                    or metadata.created_at != row["created_at"] or metadata.envelope_format_version != row["envelope_format_version"]
                    or (None if metadata.parent is None else metadata.parent.snapshot_id) != parent_id):
                raise PublicationInfrastructureError("snapshot columns disagree with decoded envelope")
            if isinstance(metadata, WorldSnapshotMetadata):
                if metadata.ref.world_uid != row["world_uid"] or metadata.ref.timeline_id != row["timeline_id"] or metadata.base_pack_hash != row["base_pack_hash"]:
                    raise PublicationInfrastructureError("world snapshot projection mismatch")
            else:
                if not isinstance(ref, PlayerSnapshotRef):
                    raise PublicationInfrastructureError("player metadata read requires a player ref")
                world = await self._world_for_player(row["operation_id"], pinned)
                if (not isinstance(world, WorldSnapshotMetadata) or row["world_uid"] != world.ref.world_uid
                        or row["timeline_id"] != world.ref.timeline_id or row["turn_id"] != world.turn_id):
                    raise PublicationInfrastructureError("player/world operation mismatch")
                if row["session_id"] is not None:
                    session = await _one(self._commits, pinned, "SELECT id, world_uid, player_character_id FROM game_sessions WHERE id=?", (row["session_id"],))
                    if session is None:
                        raise PublicationInfrastructureError("missing session audit")
                    _fields(session, uids=("id", "world_uid", "player_character_id"))
                    if session["world_uid"] != row["world_uid"] or session["player_character_id"] != ref.player_uid:
                        raise PublicationInfrastructureError("session audit owner mismatch")
            await self._validate_parent(metadata.parent, pinned)
            return metadata
