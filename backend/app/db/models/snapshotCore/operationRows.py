"""Immutable SQL rows for Snapshot core; no publication behavior or IO."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicationOperationRow:
    __table__ = "publication_operations"
    __pk__ = "operation_id"

    operation_id: str
    world_uid: str
    kind: str
    preparation_fingerprint: str


@dataclass(frozen=True)
class PublicationRequestRow:
    __table__ = "publication_requests"
    __pk__ = "operation_id"

    operation_id: str
    publication_fingerprint: str


@dataclass(frozen=True)
class PublicationOperationEventRow:
    __table__ = "publication_operation_events"
    __pk__ = "event_id"

    event_id: str
    operation_id: str
    predecessor_id: str | None
    event_seq: int
    phase: str
    fence: int


@dataclass(frozen=True)
class PublicationOutcomeRow:
    __table__ = "publication_outcomes"
    __pk__ = "operation_id"

    operation_id: str
    outcome_kind: str
    category: str | None
    format_version: int
    outcome_data: bytes
    outcome_checksum: str
