"""Coarse Pass 1.4 — local depression → lower ``surface_z``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.reliefObjects.depressionDetect import (
    detect_depression_cells,
)
from app.application.worldData.generators.terrain.reliefObjects.elevationResolve import (
    resolve_ravine_surface_z,
)
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min

if TYPE_CHECKING:
    from app.application.worldData.generators.terrain.types import SurfaceHeightmap
    from app.db.models.world import World

logger = logging.getLogger(__name__)


def apply_ravine_z(world: World, heightmap: SurfaceHeightmap) -> int:
    """Drop ``surface_z`` on local minima matching ravine policy. Returns dropped count."""
    masks = terrain_masks(world)
    policy = masks.default_ravines
    if not masks.category_enabled(policy) or not policy.autoresolve:
        return 0

    z_min = world_z_min(world)
    to_drop = detect_depression_cells(heightmap.surface_z, policy)
    for key in to_drop:
        heightmap.surface_z[key] = resolve_ravine_surface_z(
            heightmap.surface_z[key],
            z_min=z_min,
            policy=policy,
        )

    logger.debug(
        "relief_objects_ravine_z | world=%s dropped=%d",
        world.world_uid,
        len(to_drop),
    )
    return len(to_drop)
