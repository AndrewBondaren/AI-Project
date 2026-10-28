"""Computed generation behavior, independent of category scopes and cascade levels."""

from enum import StrEnum


class HydrologyExecutionMode(StrEnum):
    DISABLED = "disabled"
    DECLARED_ONLY = "declared_only"
    AUTORESOLVE = "autoresolve"
