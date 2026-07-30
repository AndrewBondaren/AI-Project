"""Explain SLOPE/SHEER (+ uphill facing hint) — tz_terrain_relief § Logging.

Shim: math + decision types live in ``terrain/relief``; this wraps FormGeometry.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    MountainFormGeometry,
)
from app.application.worldData.generators.terrain.mountains.sideFill import (
    side_fill_grade_at_xy,
)
from app.application.worldData.generators.terrain.relief.facing import uphill_facing_toward
from app.application.worldData.generators.terrain.relief.sideGradeDecision import (
    RadialGradeDecision,
    format_sides_summary,
)
from app.dataModel.terrainMasks.mountain.specs import MountainSideSpec

# Back-compat alias (mountains FormGeometry callers / tests).
SideGradeDecision = RadialGradeDecision


def explain_side_grade_at_xy(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    px: float,
    py: float,
    *,
    light_m: float,
) -> SideGradeDecision:
    """Ownership B + profile — same math as ``side_fill_fraction_at_xy``, with reason."""
    return side_fill_grade_at_xy(geometry, sides, px, py, light_m=light_m)


__all__ = [
    "SideGradeDecision",
    "explain_side_grade_at_xy",
    "format_sides_summary",
    "uphill_facing_toward",
]
