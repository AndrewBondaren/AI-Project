"""Import batch result — application SoT (RELIEF-T-21).

API may re-export; services must not import from ``api.schemas``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImportError:
    index: int
    message: str
    entity_id: str | None = None


@dataclass
class ImportResult:
    total: int
    succeeded: int
    failed: int
    errors: list[ImportError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "errors": [
                {
                    "index": e.index,
                    "entity_id": e.entity_id,
                    "message": e.message,
                }
                for e in self.errors
            ],
        }
