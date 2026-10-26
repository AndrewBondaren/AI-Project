"""Ocean default level — per-body levels are resolved on basin input (HY-12)."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.worldRow import hydrology


def resolve_z_sea(world: Any) -> int:
    """Compatibility entry point reading the WorldHydrology scalar."""
    return hydrology(world).default_water_level


def is_land(surface_z: int, z_sea: int | None = None) -> bool:
    level = resolve_z_sea(None) if z_sea is None else z_sea
    return surface_z >= level
