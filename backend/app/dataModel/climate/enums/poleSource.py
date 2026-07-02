"""Climate pole point provenance — manual vs autoresolve."""

from __future__ import annotations

from enum import Enum


class PoleSource(Enum):
    MANUAL = "manual"
    AUTORESOLVE = "autoresolve"

    @property
    def wire_value(self) -> str:
        return self.value

    def __str__(self) -> str:
        return self.wire_value
