"""River system topology role — wire enum."""

from __future__ import annotations

from enum import StrEnum


class RiverSystemRole(StrEnum):
    STEM = "stem"
    TRIBUTARY = "tributary"
    SYSTEM = "system"
