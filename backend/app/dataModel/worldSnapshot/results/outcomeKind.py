"""Core apply outcome categories; failures/recovery are not successful commits."""

from enum import StrEnum


class SnapshotApplyOutcomeKind(StrEnum):
    COMMITTED = "committed"
    CONFLICT = "conflict"
    REJECTED = "rejected"
