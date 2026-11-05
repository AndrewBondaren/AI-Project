"""Translate schema and wire locations into typed validation issues."""

from __future__ import annotations

from typing import Any, get_args

from pydantic import BaseModel, RootModel, ValidationError
from pydantic_core import ErrorDetails
from pydantic_core.core_schema import ErrorType

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.types import ImportIssue
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.validatedFieldPath import VariantSegment
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue


_PYDANTIC_ERROR_TYPES: frozenset[str] = frozenset(get_args(ErrorType))
_NO_INPUT = object()
_PYDANTIC_WRAPPER_PREFIXES = (
    "is-instance[", "function-before[", "function-after[", "function-wrap[", "function-plain[",
)


def field_issue(ctx: ResolveContext, root: type[BaseModel] | None, loc: tuple[str | int, ...],
                 message: str, code: JsonValidationCode,
                 pydantic_type: ErrorType | None = None) -> ImportIssue:
    """F01 when loc is a declared field of root; otherwise F09 at the raw wire location."""
    is_root_model = root is not None and issubclass(root, RootModel)
    model_loc = ("root", *loc) if is_root_model else loc
    path = CheckedPath.from_pydantic_loc(root, model_loc) if root is not None else None
    if path is None:
        return WireShapeIssue(code=code, location=ctx.location.child(*loc),
                              message=message, pydantic_type=pydantic_type)
    segments = path.segments[1:] if is_root_model else path.segments
    wire_path = tuple(part for part, segment in zip(loc, segments, strict=True)
                      if not isinstance(segment, VariantSegment))
    if not wire_path:
        return WireShapeIssue(code=code, location=ctx.location,
                              message=message, pydantic_type=pydantic_type)
    return JsonFieldError(code=code, path=path, location=ctx.location, wire_path=wire_path,
                          schema_id=ctx.schema_id, pydantic_type=pydantic_type, message=message)


def _input_loc(error: ErrorDetails, raw: Any) -> tuple[str | int, ...]:
    """Keep authored keys; discard Pydantic wrapper labels outside the input path."""
    loc = error["loc"]
    if raw is _NO_INPUT:
        return loc
    parts: list[str | int] = []
    for index, part in enumerate(loc):
        if isinstance(raw, dict) and part in raw:
            raw = raw[part]
        elif isinstance(raw, (list, tuple)) and isinstance(part, int) and 0 <= part < len(raw):
            raw = raw[part]
        elif (isinstance(part, str) and part.endswith("]")
              and part.startswith(_PYDANTIC_WRAPPER_PREFIXES)
              and not (error["type"] == "missing" and index == len(loc) - 1)):
            continue
        parts.append(part)
    return tuple(parts)


def _raw_row_loc(error: ErrorDetails, raw: Any) -> tuple[str | int, ...]:
    """Union branch labels do not descend into the input; authored keys do."""
    if raw is _NO_INPUT:
        return error["loc"]
    loc = error["loc"]
    missing = error["type"] == "missing"
    steps = loc[:-1] if missing else loc
    matches: dict[tuple[int, int], tuple[str | int, ...] | None] = {}

    def match(value: Any, start: int) -> tuple[str | int, ...] | None:
        if value is error["input"]:
            return loc[-1:] if missing else ()
        state = (id(value), start)
        if state in matches:
            return matches[state]
        best = None
        # Match the authored suffix first: a branch named like a dictionary
        # key precedes that key in Pydantic's loc.
        for i in range(len(steps) - 1, start - 1, -1):
            part = steps[i]
            if isinstance(value, dict) and part in value:
                child = value[part]
            elif isinstance(value, (list, tuple)) and isinstance(part, int) and 0 <= part < len(value):
                child = value[part]
            else:
                continue
            tail = match(child, i + 1)
            if tail is not None and (best is None or len(tail) + 1 > len(best)):
                best = (part, *tail)
        matches[state] = best
        return best

    path = match(raw, 0)
    return _input_loc(error, raw) if path is None else path


def _schema_issue(ctx: ResolveContext, root: type[BaseModel] | None, error: ErrorDetails,
                  prefix: tuple[str | int, ...], raw: Any) -> ImportIssue:
    kind = error["type"]
    loc = prefix + (_raw_row_loc(error, raw) if root is None else _input_loc(error, raw))
    if kind == "enum":
        return field_issue(ctx, root, loc, "unknown wire value; " + error["msg"],
                            JsonValidationCode.UNKNOWN_ENUM)
    if kind in _PYDANTIC_ERROR_TYPES:
        return field_issue(ctx, root, loc, error["msg"], JsonValidationCode.SCHEMA_VIOLATION, kind)  # type: ignore[arg-type]
    return field_issue(ctx, root, loc, error["msg"], JsonValidationCode.VALIDATION_ERROR)


def pydantic_issues(ctx: ResolveContext, root: type[BaseModel] | None, exc: ValidationError,
                    *, raw: Any = _NO_INPUT, prefix: tuple[str | int, ...] = ()) -> list[ImportIssue]:
    """C0-8: the owning validation boundary translates Pydantic errors()."""
    return [_schema_issue(ctx, root, error, prefix, raw) for error in exc.errors()]
