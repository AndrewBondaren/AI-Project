"""Shore terrain/material from world hydrology POJO — D HY-2."""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.worldRow import hydrology
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.shore import HydrologyShoreDefaults


def shore_terrain_material(world: Any) -> tuple[str, str]:
    shore = hydrology(world).default_shore
    if isinstance(shore, dict):
        shore = HydrologyShoreDefaults.model_validate(shore)
    return str(shore.system_terrain), str(shore.system_material)


def apply_shore_surface(
    role: HydrologyCellRole | None,
    z: int,
    terrain_set: set[str],
    default_terrain: str,
    *,
    shore_terrain: str,
) -> str:
    """Surface terrain for hydrology shore roles; open water stays on elevation mapping."""
    if role == HydrologyCellRole.SHORE and shore_terrain in terrain_set:
        return shore_terrain
    return default_terrain
