"""Coarse SEA/LAKE fill from surface_planning — Path A areal open water.

Invariant (narrow): do **not** overwrite light cells that already have
``hydrology_role == RIVER`` from declared corridors. Global ``WorldMapHydrologyRole.merge``
(SEA ≥ RIVER) is unchanged; this skip is only for coarse open-water paint so a declared
river survives inside a SEA macro tile.

R5b: after paint, write bathymetry ``surface_z`` (stub drop / coarse floor).
"""

from __future__ import annotations

from app.application.jsonValidation import hydrology
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.hydrology.bathymetry import resolve_open_water_surface_z
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import paint_role
from app.application.worldData.pack.bake.worldMapHydrology import world_map_hydro_role_from_cell
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

_PRESERVE_DECLARED_RIVER = frozenset({WorldMapHydrologyRole.RIVER})
_OPEN_WATER = frozenset({WorldMapHydrologyRole.SEA, WorldMapHydrologyRole.LAKE})


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
            "z_applied": 0,
        }
    scale = compose.scale
    tile_set = set(ctx.tiles)
    sea_macros = 0
    lake_macros = 0
    painted = 0
    preserved = 0
    z_applied = 0

    seas = hydrology(ctx.world).default_seas
    z_sea = resolve_z_sea(ctx.world)
    z_min = world_z_min(ctx.world)
    coarse_z_map = planning.coarse_surface_z

    for gx, gy in ctx.tiles:
        role = world_map_hydro_role_from_cell(planning.coarse_hydro.get((gx, gy)))
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

        floor_z = resolve_open_water_surface_z(
            z_sea=z_sea,
            z_min=z_min,
            policy=seas,
            coarse_z=coarse_z_map.get((gx, gy)),
        )
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
