"""Validation versus runtime resolution; separate from ResolveMode transport context."""

from enum import StrEnum


class ResolutionMode(StrEnum):
    RUNTIME = "runtime"
    VALIDATE_ONLY = "validate_only"
