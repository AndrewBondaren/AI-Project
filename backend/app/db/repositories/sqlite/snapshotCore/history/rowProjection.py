"""Pure history row/envelope projection; relation queries belong to the store."""

from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter

from app.application.encoding.canonicalCodec import content_digest
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec
from app.dataModel.patch.values import FormatVersion
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import (
    SnapshotEnvelope, WorldSnapshotMetadata, PlayerSnapshotMetadata, CreatedAtUtc,
)
from app.db.models.snapshotCore.historyRows import WorldSnapshotRow, PlayerSnapshotRow
from app.db.repositories.sqlite.shared.validation.rowValues import _fields
from app.db.repositories.sqlite.shared.validation.blobIntegrity import _checked_blob


def encode_history_row(metadata: SnapshotEnvelope, world: WorldSnapshotMetadata | None,
                       codec: SnapshotEnvelopeCodec) -> WorldSnapshotRow | PlayerSnapshotRow:
    metadata = TypeAdapter(SnapshotEnvelope).validate_python(metadata, strict=True)
    data = codec.encode(metadata)
    checksum = content_digest(data).hex()
    if isinstance(metadata, WorldSnapshotMetadata):
        return WorldSnapshotRow(metadata.ref.snapshot_id, metadata.ref.timeline_id, metadata.ref.world_uid,
            metadata.turn_id, metadata.created_at, None if metadata.parent is None else metadata.parent.snapshot_id,
            data, checksum, metadata.operation_id, metadata.envelope_format_version, metadata.base_pack_hash)
    if world is None:
        raise ValueError("player metadata requires its world metadata")
    world = WorldSnapshotMetadata.model_validate(world, strict=True)
    if world.operation_id != metadata.operation_id or world.turn_id != metadata.turn_id:
        raise ValueError("player tick does not match world tick")
    return PlayerSnapshotRow(metadata.ref.snapshot_id, metadata.ref.player_uid, world.ref.world_uid,
        world.ref.timeline_id, None, metadata.turn_id, metadata.created_at,
        None if metadata.parent is None else metadata.parent.snapshot_id, metadata.operation_id,
        metadata.envelope_format_version, data, checksum)


def decode_history_row(row: Mapping[str, Any], expected_ref: SnapshotRef,
                       codec: SnapshotEnvelopeCodec) -> SnapshotEnvelope:
    expected_ref = TypeAdapter(SnapshotRef).validate_python(expected_ref, strict=True)
    world = isinstance(expected_ref, WorldSnapshotRef)
    _fields(row, uids=(("snapshot_id", "world_uid", "timeline_id", "operation_id") if world else
            ("player_snapshot_id", "player_uid", "world_uid", "timeline_id", "operation_id")),
        optional_uids=(("parent_snapshot_id",) if world else ("parent_player_snapshot_id", "session_id")),
        positives=("turn_id", "envelope_format_version"),
        hashes=(("snapshot_checksum", "base_pack_hash") if world else ("snapshot_checksum",)))
    TypeAdapter(CreatedAtUtc).validate_python(row["created_at"], strict=True)
    TypeAdapter(FormatVersion).validate_python(row["envelope_format_version"], strict=True)
    if row["envelope_format_version"] not in codec.SUPPORTED_VERSIONS:
        raise PublicationInfrastructureError("unsupported stored snapshot format")
    metadata = codec.decode(_checked_blob(row["snapshot_data"], row["snapshot_checksum"]))
    if (metadata.ref != expected_ref or (world and not isinstance(metadata, WorldSnapshotMetadata))
            or (not world and not isinstance(metadata, PlayerSnapshotMetadata))):
        raise PublicationInfrastructureError("snapshot chain/ref does not match its envelope")
    parent_id = row["parent_snapshot_id"] if world else row["parent_player_snapshot_id"]
    identity = row["snapshot_id"] if world else row["player_snapshot_id"]
    if (metadata.ref.snapshot_id != identity or metadata.operation_id != row["operation_id"]
            or metadata.turn_id != row["turn_id"] or metadata.created_at != row["created_at"]
            or metadata.envelope_format_version != row["envelope_format_version"]
            or (None if metadata.parent is None else metadata.parent.snapshot_id) != parent_id):
        raise PublicationInfrastructureError("snapshot columns disagree with decoded envelope")
    if isinstance(metadata, WorldSnapshotMetadata):
        if (metadata.ref.world_uid != row["world_uid"] or metadata.ref.timeline_id != row["timeline_id"]
                or metadata.base_pack_hash != row["base_pack_hash"]):
            raise PublicationInfrastructureError("world snapshot projection mismatch")
    elif not isinstance(expected_ref, PlayerSnapshotRef) or metadata.ref.player_uid != row["player_uid"]:
        raise PublicationInfrastructureError("player snapshot projection mismatch")
    return metadata
