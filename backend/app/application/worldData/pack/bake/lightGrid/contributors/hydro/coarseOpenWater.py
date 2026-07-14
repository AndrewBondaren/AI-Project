"""Coarse SEA/LAKE fill from surface_planning — Path A areal open water.

Invariant (narrow): do **not** overwrite light cells that already have
``hydrology_role == RIVER`` from declared corridors. Global ``WorldMapHydrologyRole.merge``
(SEA ≥ RIVER) is unchanged; this skip is only for coarse open-water paint so a declared
river survives inside a SEA macro tile.
"""

from __future__ import annotations

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import paint_role
from app.application.worldData.pack.bake.worldMapHydrology import world_map_hydro_role_from_cell
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

_PRESERVE_DECLARED_RIVER = frozenset({WorldMapHydrologyRole.RIVER})


def apply_coarse_open_water(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
) -> dict[str, int]:
    planning = ctx.surface_planning
    if planning is None:
        return {
            "skipped_no_planning": 1,
            "sea_macros": 0,
            "lake_macros": 0,
            "cells_painted": 0,
            "river_preserved": 0,
        }
    scale = compose.scale
    tile_set = set(ctx.tiles)
    sea_macros = 0
    lake_macros = 0
    painted = 0
    preserved = 0
    for gx, gy in ctx.tiles:
        role = world_map_hydro_role_from_cell(planning.coarse_hydro.get((gx, gy)))
        if role not in (WorldMapHydrologyRole.SEA, WorldMapHydrologyRole.LAKE):
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
    return {
        "skipped_no_planning": 0,
        "sea_macros": sea_macros,
        "lake_macros": lake_macros,
        "cells_painted": painted,
        "river_preserved": preserved,
    }
