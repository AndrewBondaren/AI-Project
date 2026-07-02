"""Wire stat schema conflict resolution mode."""

from __future__ import annotations

from enum import StrEnum


class StatConflictMode(StrEnum):
    SOFT = "soft"
    MIGRATE = "migrate"
