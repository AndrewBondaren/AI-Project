"""Sample shoulder seeds on the outer ring of a painted road footprint.

SoT ring = edge of ``road_cells`` (axis ± optional dilate). Not centerline walk.
See tz_terrain_relief Q6 / Wave B1.
Empty-sample log = apply only (RELIEF-T-65).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_to_macro_local
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing

# Stable cardinal order (E,W,N,S) — Facing SoT deltas (RELIEF-T-62).
_ORTHO = tuple(
    CARDINAL_WALL_OUTWARD_DELTA[f]
    for f in (Facing.EAST, Facing.WEST, Facing.NORTH, Facing.SOUTH)
)


def sample_shoulder_cells(
    compose: LightGridCompose,
    road_cells: set[tuple[int, int]],
    *,
    tile_set: set[tuple[int, int]],
) -> list[tuple[tuple[int, int], str, int]]:
    """Emit ortho exterior neighbors of ``road_cells`` once, stable by seed xy.

    ``dz`` uses the abutment road cell (footprint edge), not the polyline axis.
    """
    if not road_cells:
        return []
    scale = compose.scale
    side = scale.side
    seen: set[tuple[int, int]] = set()
    out: list[tuple[tuple[int, int], str, int]] = []
    for lx, ly in sorted(road_cells):
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        road_cell = compose.get(gx, gy, tx, ty)
        if road_cell is None:
            continue
        road_z = int(road_cell.surface_z)
        for dx, dy in _ORTHO:
            nx, ny = lx + dx, ly + dy
            seed = (nx, ny)
            if seed in road_cells or seed in seen:
                continue
            ngx, ngy, ntx, nty = light_to_macro_local(nx, ny, scale)
            if (ngx, ngy) not in tile_set:
                continue
            if not (0 <= ntx < side and 0 <= nty < side):
                continue
            neighbor = compose.get(ngx, ngy, ntx, nty)
            if neighbor is None or not neighbor.system_terrain:
                continue
            seen.add(seed)
            out.append((
                seed,
                str(neighbor.system_terrain),
                relief_dz(road_z, neighbor.surface_z),
            ))
    out.sort(key=lambda item: item[0])
    return out
