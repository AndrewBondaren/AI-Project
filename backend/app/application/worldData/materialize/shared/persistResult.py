"""Application-layer persist counters — not HTTP import schema (WP-FIX-DEBT-9)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersistResult:
    total: int
    succeeded: int
    failed: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
        }

    @classmethod
    def from_counts(cls, total: int, succeeded: int, *, failed: int = 0) -> PersistResult:
        return cls(total=total, succeeded=succeeded, failed=failed)
