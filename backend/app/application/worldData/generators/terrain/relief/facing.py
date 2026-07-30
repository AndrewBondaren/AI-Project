"""Uphill facing helpers — tz_terrain_relief / tz_locations staircase analogy."""

from __future__ import annotations

from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing


def uphill_facing_toward(
    px: float,
    py: float,
    target_x: float,
    target_y: float,
) -> Facing | None:
    """Cardinal toward ``target`` (uphill for radial slope → mountain origin)."""
    dx = float(target_x) - float(px)
    dy = float(target_y) - float(py)
    if dx == 0.0 and dy == 0.0:
        return None
    if abs(dx) >= abs(dy):
        facing = Facing.EAST if dx > 0.0 else Facing.WEST
    else:
        facing = Facing.NORTH if dy > 0.0 else Facing.SOUTH
    return facing if facing in CARDINAL_FACINGS else None


def facing_wire(facing: Facing | None) -> str | None:
    """Wire / MapCell stamp boundary."""
    return None if facing is None else facing.value
