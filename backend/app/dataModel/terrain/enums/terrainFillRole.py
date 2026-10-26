"""Terrain use in solid column filling; independent of registry key names."""

from __future__ import annotations

from enum import StrEnum


class TerrainFillRole(StrEnum):
    SUBSURFACE = "subsurface"
    MAGMA = "magma"

    @property
    def fallback_role(self) -> TerrainFillRole | None:
        return TerrainFillRole.SUBSURFACE if self is TerrainFillRole.MAGMA else None
