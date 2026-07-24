"""Shared L0 terrain-mask helpers (forest/plains, mountain field, merge).

MaskDomain materialize runners (``run_mask_domain``, ``apply_terrain_footprint``)
live in sibling modules — import them directly to avoid light-grid cycles.
"""

from app.application.worldData.masks.mountainField import (
    is_mountain_autoresolve,
    mountain_autoresolve_score,
)
from app.application.worldData.masks.resolveForestPlains import (
    profile_for_zone_key,
    resolve_forest_plains,
    resolve_forest_plains_from_zone,
)
from app.application.worldData.masks.terrainMerge import (
    PRESERVE_HYDROLOGY_ROLES,
    may_paint_terrain,
    terrain_merge_rank,
)

__all__ = [
    "PRESERVE_HYDROLOGY_ROLES",
    "is_mountain_autoresolve",
    "may_paint_terrain",
    "mountain_autoresolve_score",
    "profile_for_zone_key",
    "resolve_forest_plains",
    "resolve_forest_plains_from_zone",
    "terrain_merge_rank",
]
