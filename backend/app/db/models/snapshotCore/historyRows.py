"""Immutable SQL rows for Snapshot core; no publication behavior or IO."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorldSnapshotRow:
    __table__ = "world_snapshots"
    __pk__ = "snapshot_id"

    snapshot_id: str
    timeline_id: str
    world_uid: str
    turn_id: int
    created_at: str
    parent_snapshot_id: str | None
    snapshot_data: bytes
    snapshot_checksum: str
    operation_id: str
    envelope_format_version: int
    base_pack_hash: str


@dataclass(frozen=True)
class PlayerSnapshotRow:
    __table__ = "player_snapshots"
    __pk__ = "player_snapshot_id"

    player_snapshot_id: str
    player_uid: str
    world_uid: str
    timeline_id: str
    session_id: str | None
    turn_id: int
    created_at: str
    parent_player_snapshot_id: str | None
    operation_id: str
    envelope_format_version: int
    snapshot_data: bytes
    snapshot_checksum: str
