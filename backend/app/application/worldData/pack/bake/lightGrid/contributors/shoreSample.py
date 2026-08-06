"""Sample shore ribbon seeds — Wave D2.

``WorldMapHydrologyRole.SHORE`` cells = abutment (ref); landward ortho neighbor = seed.
Does not own hydro paint — only consumes roles.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_to_macro_local
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonSampleUtil import (
    CARDINAL_ORTHO_DELTAS,
    iter_compose_cells,
    landward_seed_blocked,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole


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
    for xy, cell in iter_compose_cells(compose, tile_set):
        if cell.hydrology_role is not WorldMapHydrologyRole.SHORE:
            continue
        shore_refs.append((xy, int(cell.surface_z)))

    for (lx, ly), shore_z in shore_refs:
        for dx, dy in CARDINAL_ORTHO_DELTAS:
            seed = (lx + dx, ly + dy)
            if seed in seen_seeds:
                continue
            ngx, ngy, ntx, nty = light_to_macro_local(seed[0], seed[1], scale)
            if (ngx, ngy) not in tile_set:
                continue
            if not (0 <= ntx < side and 0 <= nty < side):
                continue
            neighbor = compose.get(ngx, ngy, ntx, nty)
            if neighbor is None:
                continue
            if landward_seed_blocked(neighbor, road_key=road_key):
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
