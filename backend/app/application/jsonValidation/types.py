"""Import validation result types and the 422 wire mapper (F09).

Plan: ``.cursor/plans/error-contracts-1.md`` jsonValidation D1. Wire strings
appear only in ``import_validation_http_detail``.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, RootModel, TypeAdapter

from app.dataModel.fields.validatedFieldPath import FieldSegment, IndexSegment, KeySegment, ModelIdentity
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

type ImportIssue = FieldPathError[Any] | WireShapeIssue

_ISSUES: TypeAdapter[tuple[ImportIssue, ...]] = TypeAdapter(tuple[ImportIssue, ...])


def validate_import_issues(issues: tuple[ImportIssue, ...]) -> tuple[ImportIssue, ...]:
    """Carrier admission for request-local issue containers."""
    return _ISSUES.validate_python(issues, strict=True)


@dataclass
class ResolveReport:
    """Request-local diagnostics; domain dependencies are supplied separately."""
    issues: list[ImportIssue] = field(default_factory=list)


class ImportValidationError(Exception):
    def __init__(self, errors: Iterable[ImportIssue]) -> None:
        self.errors: list[ImportIssue] = list(_ISSUES.validate_python(tuple(errors), strict=True))
        super().__init__("; ".join(f"{'.'.join(str(p) for p in wire_loc(e))}: {e.message}" for e in self.errors))


@dataclass(frozen=True)
class ImportValidationReport:
    """Completed, read-only import validation; no reservation or persistence."""
    issues: tuple[ImportIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", _ISSUES.validate_python(self.issues, strict=True))

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {"validate_only": True, "valid": self.valid,
                "issues": import_validation_http_detail(ImportValidationError(self.issues))}


def _model_of(identity: ModelIdentity) -> type[BaseModel]:
    owner: Any = sys.modules[identity.module]
    for name in identity.qualname.split("."):
        owner = getattr(owner, name)
    return owner


def _wire_name(segment: FieldSegment) -> str:
    alias = _model_of(segment.owner).model_fields[segment.name].alias
    return alias if isinstance(alias, str) else segment.name


def wire_loc(issue: ImportIssue) -> tuple[str | int, ...]:
    if isinstance(issue, WireShapeIssue):
        return issue.location.parts
    flat: list[str | int] = []
    for segment in issue.path.segments:
        if isinstance(segment, FieldSegment):
            if segment.name == "root" and issubclass(_model_of(segment.owner), RootModel):
                continue
            flat.append(_wire_name(segment))
        elif isinstance(segment, IndexSegment):
            flat.append(segment.index)
        elif isinstance(segment, KeySegment):
            flat.append(segment.key)
    prefix = issue.location.parts if isinstance(issue, JsonFieldError) else ()
    return (*prefix, *flat)


def _wire_code(issue: ImportIssue) -> object:
    if isinstance(issue, (JsonFieldError, WireShapeIssue)) and issue.code is JsonValidationCode.SCHEMA_VIOLATION:
        return issue.pydantic_type
    return issue.code.value


def import_validation_http_detail(exc: ImportValidationError) -> list[dict[str, object]]:
    detail: list[dict[str, object]] = []
    for issue in exc.errors:
        item: dict[str, object] = {"loc": list(wire_loc(issue)), "msg": issue.message, "code": _wire_code(issue)}
        if isinstance(issue, JsonFieldError) and issue.schema_id:
            item["schema_id"] = issue.schema_id
        detail.append(item)
    return detail
