"""Immutable SQL rows for Snapshot core; no publication behavior or IO."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArtifactLeaseEventRow:
    __table__ = "artifact_lease_events"
    __pk__ = "event_id"

    event_id: str
    operation_id: str
    predecessor_id: str | None
    event_seq: int
    fence: int
    admission_open: bool = field(metadata={"db_type": "bool"})


@dataclass(frozen=True)
class ArtifactWriterClaimRow:
    __table__ = "artifact_writer_claims"
    __pk__ = "event_id"

    event_id: str
    artifact_id: str
    operation_id: str
    fence: int
    predecessor_id: str | None
    event_seq: int
    event_kind: str
