"""Per-field import policy for master-data POJOs."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, get_args, get_origin


class FieldPolicy(StrEnum):
    """How import/validate treats a field when JSON is incomplete or invalid."""

    STRICT_REQUIRED = "strict_required"
    """Missing key → 422."""

    GRACE_NORMALIZE = "grace_normalize"
    """Missing/null/legacy → fill canonical default; persist explicit value."""

    GRACE_WARN = "grace_warn"
    """Accept with warning (runtime or import warn list)."""

    IGNORE = "ignore"
    """Unknown sibling keys stripped; optional nested omitted without error."""


# Wire import annotations (Field Contract Registry → POJO metadata).
type OptionalOnWire[T] = Annotated[T, FieldPolicy.GRACE_NORMALIZE]
"""Key may be absent on import; normalize fills canonical default."""

type StrictOnWire[T] = Annotated[T, FieldPolicy.STRICT_REQUIRED]
"""Key/value must pass strict validator; missing or invalid → reject."""


def field_policy(annotation: Any) -> FieldPolicy | None:
    """Extract FieldPolicy from OptionalOnWire / StrictOnWire annotation."""
    if hasattr(annotation, "__value__"):
        annotation = annotation.__value__

    if get_origin(annotation) is Annotated:
        for meta in get_args(annotation)[1:]:
            if isinstance(meta, FieldPolicy):
                return meta
    return None
