"""Upsample L0 parent light surface_z → fine meter heightmap (WP-PERF-22)."""

from __future__ import annotations

from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.coordinates.worldTile import (
    fine_bbox_for_tile,
)
from app.application.worldData.generators.terrain.passes.lightSurfaceRefine import refine_light_surface
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
from app.db.models.world import World


def upsample_from_parent_light(
    parent: ParentLightTile,
    world: World,
    *,
    policy: ParentLightRefinePolicy | None = None,
) -> dict[tuple[int, int], int]:
    """Resample L0 ``surface_z`` to meter grid; detail noise; clamp to ±z_band."""
    return refine_light_surface(parent.gx, parent.gy,
        SurfaceGridSettings(fine_span=parent.tile_macro, light_side=parent.side), parent.surface_z_at,
        seed=world_seed(world), z_min=world_z_min(world), z_max=world_z_max(world),
        policy=policy or ParentLightRefinePolicy.canonical_defaults())



def fine_bbox_for_parent(parent: ParentLightTile):
    return fine_bbox_for_tile(parent.gx, parent.gy, parent.tile_macro)
