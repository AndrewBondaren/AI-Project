"""Per-field import annotation policy for master-data POJOs."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, get_args, get_origin


class AnnotationPolicy(StrEnum):
    """How import/validate treats a field when JSON is incomplete or invalid."""

    STRICT_REQUIRED = "strict_required"
    """Strict validation — missing or invalid wire value → reject (import) / warn (runtime)."""

    GRACE_NORMALIZE = "grace_normalize"
    """Same as unannotated: missing/null/invalid → ``Field`` default fallback."""

    GRACE_WARN = "grace_warn"
    """Invalid → warning + ``Field`` default fallback."""

    IGNORE = "ignore"
    """Do not apply defaults — wire value only if present."""


type StrictOnWire[T] = Annotated[T, AnnotationPolicy.STRICT_REQUIRED]
"""Strict validation on this field only."""

type OptionalOnWire[T] = Annotated[T, AnnotationPolicy.GRACE_NORMALIZE]
"""Missing/null/invalid → field default fallback (same as no annotation)."""

type IgnoreOnWire[T] = Annotated[T, AnnotationPolicy.IGNORE]
"""No default fill — pass through wire value when present."""


def field_policy(annotation: Any) -> AnnotationPolicy | None:
    """Extract AnnotationPolicy from StrictOnWire / OptionalOnWire / IgnoreOnWire."""
    if hasattr(annotation, "__value__"):
        annotation = annotation.__value__

    if get_origin(annotation) is Annotated:
        for meta in get_args(annotation)[1:]:
            if isinstance(meta, AnnotationPolicy):
                return meta
    return None
