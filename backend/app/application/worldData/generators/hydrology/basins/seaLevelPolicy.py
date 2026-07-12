"""Sea level reference — D HY-2. See docs/tz_terrain_hydrology.md § z_sea."""

from __future__ import annotations

from typing import Any


def resolve_z_sea(world: Any) -> int:
    """v1: global sea level at z=0."""
    return 0


def is_land(surface_z: int, z_sea: int | None = None) -> bool:
    level = resolve_z_sea(None) if z_sea is None else z_sea
    return surface_z > level
