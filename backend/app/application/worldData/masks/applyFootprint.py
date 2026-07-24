"""Shared footprint writers — tz_map_light_bake § MaskDomain materialize."""

from __future__ import annotations

from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.terrainMerge import (
    PRESERVE_HYDROLOGY_ROLES,
    may_paint_terrain,
)
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks


def apply_terrain_footprint(
    compose: LightGridCompose,
    footprint: MaskFootprint,
    *,
    system_terrain: str,
    masks: WorldTerrainMasks,
    tile_set: set[tuple[int, int]] | None = None,
    preserve_hydro: bool = True,
) -> int:
    """Paint ``system_terrain`` via merge rank — sole shared terrain apply path."""
    painted = 0
    for ref in footprint.cells:
        if tile_set is not None and (ref.gx, ref.gy) not in tile_set:
            continue
        cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
        if preserve_hydro and cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
            continue
        if not may_paint_terrain(cell.system_terrain, system_terrain, masks):
            continue
        cell.system_terrain = system_terrain
        painted += 1
    return painted


def apply_location_pins(
    compose: LightGridCompose,
    footprint: MaskFootprint,
    *,
    pin_index: int,
    tile_set: set[tuple[int, int]] | None = None,
) -> int:
    """Stamp ``location_pin`` (nearest / lower index wins). ``pin_index`` from bake ctx."""
    stamped = 0
    for ref in footprint.cells:
        if tile_set is not None and (ref.gx, ref.gy) not in tile_set:
            continue
        cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
        if cell.location_pin is None or pin_index < cell.location_pin:
            cell.location_pin = pin_index
            stamped += 1
    return stamped


def light_cell_ref_set(
    cells: set[tuple[int, int]] | frozenset[tuple[int, int]],
    *,
    side: int,
    tile_set: set[tuple[int, int]] | None = None,
) -> frozenset[LightCellRef]:
    """Absolute light (lx, ly) → ``LightCellRef`` filtered by optional tile set."""
    out: set[LightCellRef] = set()
    for lx, ly in cells:
        gx, gy = lx // side, ly // side
        if tile_set is not None and (gx, gy) not in tile_set:
            continue
        out.add(LightCellRef(gx, gy, lx % side, ly % side))
    return frozenset(out)
