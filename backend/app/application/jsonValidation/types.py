"""Import validation result types and the 422 wire mapper (F09).

Plan: ``.cursor/plans/error-contracts-1.md`` jsonValidation D1. Wire strings
appear only in ``import_validation_http_detail``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter

from app.dataModel.fields.validatedFieldPath import FieldSegment, IndexSegment, KeySegment
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

type ImportIssue = FieldPathError[Any] | WireShapeIssue

_ISSUES: TypeAdapter[tuple[ImportIssue, ...]] = TypeAdapter(tuple[ImportIssue, ...])


def validate_import_issues(issues: tuple[ImportIssue, ...]) -> tuple[ImportIssue, ...]:
    """Carrier admission plus EC-06 deep immutability for issue containers."""
    admitted = _ISSUES.validate_python(issues, strict=True)
    for issue in admitted:
        validate_immutable(issue)
    return admitted


@dataclass
class ResolveReport:
    """Request-local diagnostics; domain dependencies are supplied separately."""
    issues: list[ImportIssue] = field(default_factory=list)


class ImportValidationError(Exception):
    def __init__(self, errors: Iterable[ImportIssue]) -> None:
        self.errors: list[ImportIssue] = list(validate_import_issues(tuple(errors)))
        super().__init__("; ".join(f"{'.'.join(str(p) for p in wire_loc(e))}: {e.message}" for e in self.errors))


@dataclass(frozen=True)
class ImportValidationReport:
    """Completed, read-only import validation; no reservation or persistence."""
    issues: tuple[ImportIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", validate_import_issues(self.issues))

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {"validate_only": True, "valid": self.valid,
                "issues": _wire_detail(self.issues)}


def wire_loc(issue: ImportIssue) -> tuple[str | int, ...]:
    if isinstance(issue, WireShapeIssue):
        return issue.location.parts
    if isinstance(issue, JsonFieldError):
        return (*issue.location.parts, *issue.wire_path)
    location = getattr(issue, "location", None)
    flat: list[str | int] = list(location.parts) if isinstance(location, WireLocation) else []
    for segment in issue.path.segments:
        if isinstance(segment, FieldSegment):
            flat.append(segment.name)
        elif isinstance(segment, IndexSegment):
            flat.append(segment.index)
        elif isinstance(segment, KeySegment):
            flat.append(segment.key)
    return tuple(flat)


def _wire_code(issue: ImportIssue) -> object:
    if isinstance(issue, (JsonFieldError, WireShapeIssue)) and issue.code is JsonValidationCode.SCHEMA_VIOLATION:
        return issue.pydantic_type
    return issue.code.value


def import_validation_http_detail(exc: ImportValidationError) -> list[dict[str, object]]:
    return _wire_detail(exc.errors)


def _wire_detail(issues: Iterable[ImportIssue]) -> list[dict[str, object]]:
    detail: list[dict[str, object]] = []
    for issue in issues:
        item: dict[str, object] = {"loc": list(wire_loc(issue)), "msg": issue.message, "code": _wire_code(issue)}
        schema_id = getattr(issue, "schema_id", None)
        if isinstance(schema_id, str) and schema_id:
            item["schema_id"] = schema_id
        detail.append(item)
    return detail
