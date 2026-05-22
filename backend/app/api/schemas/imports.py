from dataclasses import dataclass, field
from pydantic import BaseModel


class PathImportRequest(BaseModel):
    path: str


@dataclass
class ImportError:
    index:   int
    message: str


@dataclass
class ImportResult:
    total:     int
    succeeded: int
    failed:    int
    errors:    list[ImportError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total":     self.total,
            "succeeded": self.succeeded,
            "failed":    self.failed,
            "errors":    [{"index": e.index, "message": e.message} for e in self.errors],
        }
