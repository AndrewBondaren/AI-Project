"""Upsample L0 parent light categorical fields → fine meter map.

Nearest only. ``upsample_terrain_from_parent_light`` = terrain mask carry
(``system_terrain`` only — docs/tz_world_pack_storage.md). Facing upsample
is a separate contract. Grade uid — R36u detailed generate, not L0 carry.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from app.application.worldData.generators.coordinates.worldTile import world_meter_xy
from app.application.worldData.generators.terrain.resolveWorldMapTerrain import (
    resolve_world_map_terrain,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.world import World

T = TypeVar("T")


def _require_categorical_nearest(policy: ParentLightRefinePolicy) -> None:
    if policy.categorical_resample != "nearest":
        raise ValueError(
            f"categorical_resample={policy.categorical_resample!r} unsupported; only 'nearest'",
        )


def _upsample_optional(
    parent: ParentLightTile,
    *,
    policy: ParentLightRefinePolicy | None,
    read: Callable[[WorldMapCellWire], T | None],
) -> dict[tuple[int, int], T]:
    """Nearest light→meter for optional categorical attrs (omit unset)."""
    pol = policy or ParentLightRefinePolicy.canonical_defaults()
    _require_categorical_nearest(pol)
    tile_m = parent.tile_m
    out: dict[tuple[int, int], T] = {}
    for ly in range(tile_m):
        for lx in range(tile_m):
            xm, ym = world_meter_xy(parent.gx, parent.gy, lx, ly, tile_m)
            tx, ty = parent.meters_to_tx_ty(xm, ym)
            cell = parent.cell_at(tx, ty)
            if cell is None:
                continue
            value = read(cell)
            if value is not None:
                out[(xm, ym)] = value
    return out


def upsample_terrain_from_parent_light(
    parent: ParentLightTile,
    world: World,
    *,
    policy: ParentLightRefinePolicy | None = None,
) -> dict[tuple[int, int], str]:
    """Resample L0 ``system_terrain`` to meter grid — nearest light cell only."""
    pol = policy or ParentLightRefinePolicy.canonical_defaults()
    _require_categorical_nearest(pol)
    tile_m = parent.tile_m
    out: dict[tuple[int, int], str] = {}
    for ly in range(tile_m):
        for lx in range(tile_m):
            xm, ym = world_meter_xy(parent.gx, parent.gy, lx, ly, tile_m)
            tx, ty = parent.meters_to_tx_ty(xm, ym)
            cell = parent.cell_at(tx, ty)
            out[(xm, ym)] = resolve_world_map_terrain(world, cell)
    return out


def upsample_facing_from_parent_light(
    parent: ParentLightTile,
    *,
    policy: ParentLightRefinePolicy | None = None,
) -> dict[tuple[int, int], Facing]:
    """Resample L0 ``system_facing`` to meter grid — nearest; omit unset columns."""
    return _upsample_optional(
        parent,
        policy=policy,
        read=lambda c: c.system_facing,
    )
