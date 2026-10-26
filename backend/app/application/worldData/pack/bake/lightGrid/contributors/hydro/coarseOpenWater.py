"""Coarse SEA/LAKE fill from the final frozen hydrology plan — Path A areal open water.

Invariant (narrow): do **not** overwrite light cells that already have
``hydrology_role == RIVER`` from declared corridors. Global ``WorldMapHydrologyRole.merge``
(SEA ≥ RIVER) is unchanged; this skip is only for coarse open-water paint so a declared
river survives inside a SEA macro tile.

Copy the resolved coarse floor; L0 never synthesizes bathymetry.
"""

from __future__ import annotations

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import paint_role
from app.application.worldData.pack.bake.l0.worldMapHydrology import world_map_hydro_role_from_cell
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole

_PRESERVE_DECLARED_RIVER = frozenset({WorldMapHydrologyRole.RIVER})
_OPEN_WATER = frozenset({WorldMapHydrologyRole.SEA, WorldMapHydrologyRole.LAKE})


def apply_coarse_open_water(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
) -> dict[str, int]:
    planning = ctx.require_surface_bundle().hydrology.payload
    scale = compose.scale
    tile_set = set(ctx.tiles)
    sea_macros = 0
    lake_macros = 0
    painted = 0
    preserved = 0
    z_applied = 0

    coarse_z_map: dict[tuple[int, int], int] = {(ref.gx, ref.gy): z for ref, z in planning.coarse_surface_z}
    coarse_hydro = {(int(ref.gx), int(ref.gy)): hydro for ref, hydro in planning.coarse_hydro}
    # Final post-river envelope only.

    for gx, gy in ctx.tiles:
        role = world_map_hydro_role_from_cell(coarse_hydro.get((gx, gy)))
        if role not in _OPEN_WATER:
            continue
        if role is WorldMapHydrologyRole.SEA:
            sea_macros += 1
        else:
            lake_macros += 1
        fill = {
            (gx * scale.side + tx, gy * scale.side + ty)
            for ty in range(scale.side)
            for tx in range(scale.side)
        }
        n, p = paint_role(
            compose,
            fill,
            role,
            tile_set=tile_set,
            preserve=_PRESERVE_DECLARED_RIVER,
        )
        painted += n
        preserved += p

        floor_z = coarse_z_map.get((gx, gy))
        if floor_z is None:
            continue
        for lx, ly in fill:
            ngx = lx // scale.side
            ngy = ly // scale.side
            ntx = lx % scale.side
            nty = ly % scale.side
            if (ngx, ngy) not in tile_set:
                continue
            cell = compose.get(ngx, ngy, ntx, nty)
            if cell is None or cell.hydrology_role not in _OPEN_WATER:
                continue
            cell.surface_z = floor_z
            z_applied += 1

    return {
        "skipped_no_planning": 0,
        "sea_macros": sea_macros,
        "lake_macros": lake_macros,
        "cells_painted": painted,
        "river_preserved": preserved,
        "z_applied": z_applied,
    }
