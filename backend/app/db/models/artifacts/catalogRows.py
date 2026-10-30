"""Immutable SQL rows for Snapshot core; no publication behavior or IO."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactCatalogRow:
    __table__ = "artifact_catalog"
    __pk__ = "artifact_id"

    artifact_id: str
    kind: str
    format_key: str
    format_version: int
    content_hash: str
    nbytes: int
    row_count: int | None


@dataclass(frozen=True)
class ArtifactStorageEventRow:
    __table__ = "artifact_storage_events"
    __pk__ = "event_id"

    event_id: str
    artifact_id: str
    predecessor_id: str | None
    event_seq: int
    kind: str
