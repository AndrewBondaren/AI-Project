"""Upsample L0 parent light ``system_terrain`` → fine meter map (terrain mask carry).

Nearest only (categorical). See docs/tz_world_pack_storage.md § Terrain mask carry.
"""

from __future__ import annotations

from app.application.worldData.generators.coordinates.worldTile import world_meter_xy
from app.application.worldData.generators.terrain.resolveWorldMapTerrain import (
    resolve_world_map_terrain,
)
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.db.models.world import World


def upsample_terrain_from_parent_light(
    parent: ParentLightTile,
    world: World,
    *,
    policy: ParentLightRefinePolicy | None = None,
) -> dict[tuple[int, int], str]:
    """Resample L0 ``system_terrain`` to meter grid — nearest light cell only."""
    pol = policy or ParentLightRefinePolicy.canonical_defaults()
    if pol.terrain_resample != "nearest":
        raise ValueError(
            f"terrain_resample={pol.terrain_resample!r} unsupported; only 'nearest'",
        )
    tile_m = parent.tile_m
    out: dict[tuple[int, int], str] = {}
    for ly in range(tile_m):
        for lx in range(tile_m):
            xm, ym = world_meter_xy(parent.gx, parent.gy, lx, ly, tile_m)
            tx, ty = parent.meters_to_tx_ty(xm, ym)
            cell = parent.cell_at(tx, ty)
            out[(xm, ym)] = resolve_world_map_terrain(world, cell)
    return out
