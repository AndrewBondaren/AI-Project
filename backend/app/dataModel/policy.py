"""Per-field import policy for master-data POJOs."""

from __future__ import annotations

from enum import StrEnum


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
