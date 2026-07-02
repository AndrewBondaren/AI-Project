"""Import validation result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldPathError:
    path: tuple[str | int, ...]
    message: str
    schema_id: str | None = None
    code: str | None = None


class ImportValidationError(Exception):
    def __init__(self, errors: list[FieldPathError]) -> None:
        self.errors = errors
        super().__init__(
            "; ".join(f"{'.'.join(str(p) for p in e.path)}: {e.message}" for e in errors),
        )


def _error_code(err: FieldPathError) -> str:
    if err.code:
        return err.code
    msg = err.message.lower()
    if "strict" in msg:
        return "STRICT_REQUIRED"
    if msg == "expected list":
        return "EXPECTED_LIST"
    if msg == "expected object":
        return "EXPECTED_OBJECT"
    if "ref-w" in msg.lower() or err.code == "REF_W_UNKNOWN":
        return "REF_W_UNKNOWN"
    return "VALIDATION_ERROR"


def import_validation_http_detail(exc: ImportValidationError) -> list[dict[str, object]]:
    detail: list[dict[str, object]] = []
    for err in exc.errors:
        item: dict[str, object] = {
            "loc": list(err.path),
            "msg": err.message,
            "code": _error_code(err),
        }
        if err.schema_id:
            item["schema_id"] = err.schema_id
        detail.append(item)
    return detail
