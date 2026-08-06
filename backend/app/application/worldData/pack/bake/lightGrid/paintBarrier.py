"""Force barrier ``system_terrain`` on light cells — RELIEF-BAR-1.

Barrier is not a MaskDomain (no merge-rank). **Write-only:** caller filters
placement (road / grade / pin / hydro / existing barrier).
"""

from __future__ import annotations

from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_to_macro_local
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

_DEFAULT_BARRIER = WorldTerrainRegistry.require_engine_terrain_key("wall")


def stamp_barrier_terrain(
    compose: LightGridCompose,
    light_cells: set[tuple[int, int]],
    system_terrain: str = _DEFAULT_BARRIER,
    *,
    tile_set: set[tuple[int, int]],
) -> int:
    """Set ``system_terrain`` on pre-cleared cells. Returns cells written."""
    scale = compose.scale
    painted = 0
    for lx, ly in sorted(light_cells):
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        if not (0 <= tx < scale.side and 0 <= ty < scale.side):
            continue
        cell = compose.ensure(gx, gy, tx, ty)
        cell.system_terrain = system_terrain
        painted += 1
    return painted
