"""Sample shore ribbon seeds — Wave D2.

``WorldMapHydrologyRole.SHORE`` cells = abutment (ref); landward ortho neighbor = seed.
Does not own hydro paint — only consumes roles (tz_terrain_relief / hydrology SoT).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz
from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_to_macro_local
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole

_ORTHO = tuple(
    CARDINAL_WALL_OUTWARD_DELTA[f]
    for f in (Facing.EAST, Facing.WEST, Facing.NORTH, Facing.SOUTH)
)


def sample_shore_cells(
    compose: LightGridCompose,
    *,
    tile_set: set[tuple[int, int]],
    road_key: str,
) -> tuple[list[tuple[tuple[int, int], str, int]], set[tuple[int, int]]]:
    """Return (samples, ref_cells) for landward seeds of SHORE role cells."""
    scale = compose.scale
    side = scale.side
    samples: list[tuple[tuple[int, int], str, int]] = []
    ref_cells: set[tuple[int, int]] = set()
    seen_seeds: set[tuple[int, int]] = set()

    shore_refs: list[tuple[tuple[int, int], int]] = []
    for gx, gy in sorted(tile_set):
        for ty in range(side):
            for tx in range(side):
                cell = compose.get(gx, gy, tx, ty)
                if cell is None:
                    continue
                if cell.hydrology_role is not WorldMapHydrologyRole.SHORE:
                    continue
                lx = gx * side + tx
                ly = gy * side + ty
                shore_refs.append(((lx, ly), int(cell.surface_z)))

    for (lx, ly), shore_z in shore_refs:
        for dx, dy in _ORTHO:
            seed = (lx + dx, ly + dy)
            if seed in seen_seeds:
                continue
            ngx, ngy, ntx, nty = light_to_macro_local(seed[0], seed[1], scale)
            if (ngx, ngy) not in tile_set:
                continue
            if not (0 <= ntx < side and 0 <= nty < side):
                continue
            neighbor = compose.get(ngx, ngy, ntx, nty)
            if neighbor is None or not neighbor.system_terrain:
                continue
            if neighbor.system_terrain == road_key:
                continue
            if neighbor.system_grade_uid:
                continue
            if neighbor.location_pin is not None:
                continue
            # Landward: not open water / river / sea roles
            if neighbor.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
                continue
            if neighbor.hydrology_role is WorldMapHydrologyRole.SHORE:
                continue
            seen_seeds.add(seed)
            ref_cells.add((lx, ly))
            samples.append((
                seed,
                str(neighbor.system_terrain),
                relief_dz(shore_z, neighbor.surface_z),
            ))

    samples.sort(key=lambda item: item[0])
    return samples, ref_cells
