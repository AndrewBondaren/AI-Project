"""Import validation result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldPathError:
    path: tuple[str | int, ...]
    message: str


class ImportValidationError(Exception):
    def __init__(self, errors: list[FieldPathError]) -> None:
        self.errors = errors
        super().__init__(
            "; ".join(f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in errors),
        )


def import_validation_http_detail(exc: ImportValidationError) -> list[dict[str, object]]:
    return [{"loc": list(err.path), "msg": err.message} for err in exc.errors]
