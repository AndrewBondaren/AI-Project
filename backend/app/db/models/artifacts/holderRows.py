"""Immutable SQL rows for Snapshot core; no publication behavior or IO."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactHolderEventRow:
    __table__ = "artifact_holder_events"
    __pk__ = "event_id"

    event_id: str
    artifact_id: str
    holder_kind: str
    operation_id: str | None
    fence: int | None
    retained_artifact_id: str | None
    world_snapshot_id: str | None
    player_snapshot_id: str | None
    predecessor_id: str | None
    event_seq: int
    event_kind: str
