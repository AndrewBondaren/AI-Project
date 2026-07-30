"""Relief grade kinds — tz_terrain_relief (SLOPE | SHEER)."""

from __future__ import annotations

from enum import StrEnum


class ReliefSideKind(StrEnum):
    """Graded face vs vertical face — not landcover / system_terrain."""

    SHEER = "sheer"
    SLOPE = "slope"
