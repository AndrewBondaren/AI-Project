"""Shared local-depression detect for ravine coarse / light (tz_map_light_bake)."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from app.dataModel.terrainMasks.worldTerrainMasks import RavinesCategoryPolicy

NEIGHBORS_8: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def detect_depression_cells(
    surface_z: Mapping[tuple[int, int], int],
    policy: RavinesCategoryPolicy,
    *,
    keys: list[tuple[int, int]] | None = None,
    neighbor_z: Callable[[tuple[int, int]], list[int]] | None = None,
) -> list[tuple[int, int]]:
    """
    Cells that are local minima vs neighbors by ``min_drop`` / ``min_neighbors``.

    Default neighbor lookup uses 8-adjacent keys inside ``surface_z``.
    Light callers pass ``neighbor_z`` when the grid spans multiple macro tiles.
    """
    min_drop = int(policy.min_drop)
    min_neighbors = int(policy.min_neighbors)
    scan = keys if keys is not None else list(surface_z.keys())

    def _default_neighbors(key: tuple[int, int]) -> list[int]:
        gx, gy = key
        out: list[int] = []
        for dx, dy in NEIGHBORS_8:
            n = (gx + dx, gy + dy)
            if n in surface_z:
                out.append(surface_z[n])
        return out

    resolve = neighbor_z or _default_neighbors
    hits: list[tuple[int, int]] = []
    for key in scan:
        if key not in surface_z:
            continue
        zs = resolve(key)
        if len(zs) < min_neighbors:
            continue
        if surface_z[key] <= min(zs) - min_drop:
            hits.append(key)
    return hits
