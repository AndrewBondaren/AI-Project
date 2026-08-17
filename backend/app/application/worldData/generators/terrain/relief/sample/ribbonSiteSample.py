"""Shared ribbon site sample — R36u-T-7 (meter + leftover L0).

Deprecated v1 occupancy (R38). SoT discover is R41
(``.cursor/plans/relief-pipeline-v2.md``). Still the live bake path.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from app.application.worldData.generators.terrain.relief.geom.facing import CARDINAL_ORTHO_DELTAS
from app.application.worldData.generators.terrain.relief.geom.outward import relief_dz
from app.application.worldData.generators.terrain.relief.geom.terrainDescent import (
    TERRAIN_RAY_MIN_ABS_DZ,
    measure_terrain_descent,
)

Coord = tuple[int, int]
NeighborSite = Callable[[Coord], tuple[str, int] | None]
ZAt = Callable[[Coord], int | None]


class SampleCell(NamedTuple):
    """One ribbon seed: downhill/landward cell + terrain + measured Δz.

    ``path_length`` — terrain-ray L for open_land peaks (omit → pick uses
    envelope only). Road/shore/ravine leave the default.
    """

    xy: Coord
    terrain: str
    dz: int
    path_length: int | None = None


def sample_downhill_land_sites(
    land: dict[Coord, tuple[str, int]],
    *,
    deltas: tuple[tuple[int, int], ...] = CARDINAL_ORTHO_DELTAS,
) -> tuple[list[SampleCell], set[Coord]]:
    """Deprecated v1: uphill land = ref; downhill ortho neighbor = seed.

    SoT: uncovered rims + occupancy (C39), not every downhill step.
    """
    samples: list[SampleCell] = []
    ref_cells: set[Coord] = set()
    seen_seeds: set[Coord] = set()

    for (lx, ly), (_terrain_hi, z_hi) in sorted(land.items()):
        for dx, dy in deltas:
            seed = (lx + dx, ly + dy)
            low = land.get(seed)
            if low is None:
                continue
            terrain_lo, z_lo = low
            if z_hi <= z_lo:
                continue
            if seed in seen_seeds:
                continue
            seen_seeds.add(seed)
            ref_cells.add((lx, ly))
            samples.append(SampleCell(seed, terrain_lo, relief_dz(z_hi, z_lo)))

    samples.sort(key=lambda item: item.xy)
    return samples, ref_cells


def _is_local_peak(
    xy: Coord,
    land: dict[Coord, tuple[str, int]],
    deltas: tuple[tuple[int, int], ...],
) -> bool:
    z = land[xy][1]
    x, y = xy
    for dx, dy in deltas:
        nb = land.get((x + dx, y + dy))
        if nb is not None and nb[1] > z:
            return False
    return True


def sample_peak_land_sites(
    land: dict[Coord, tuple[str, int]],
    *,
    z_at: ZAt | None = None,
    crests_extra: set[Coord] | None = None,
    seed_ok: Callable[[Coord], bool] | None = None,
    deltas: tuple[tuple[int, int], ...] = CARDINAL_ORTHO_DELTAS,
) -> tuple[list[SampleCell], set[Coord]]:
    """Deprecated v1: crest (local peak or cascade) × cardinal facing → seed.

    SoT: rim with descent (R41), not hunt local max (R38). ``|dz| <
    TERRAIN_RAY_MIN_ABS_DZ`` (4→3) is left as the heightmap. ``|dz| >= 2``:
    L = terrain ray until a voxel blocks; ``h = z_crest − z_end``.
    """
    lookup = z_at or (lambda cell: None if cell not in land else land[cell][1])
    extra = crests_extra or set()
    accept = seed_ok or (lambda cell: cell in land)
    samples: list[SampleCell] = []
    ref_cells: set[Coord] = set()
    seen_seeds: set[Coord] = set()
    crests = [
        xy for xy in sorted(land)
        if xy in extra or _is_local_peak(xy, land, deltas)
    ]
    for (px, py) in crests:
        z_crest = land[(px, py)][1]
        for dx, dy in deltas:
            seed = (px + dx, py + dy)
            if seed in seen_seeds or not accept(seed):
                continue
            site = land.get(seed)
            if site is None:
                continue
            terrain_lo, z_first = site
            if z_crest - int(z_first) < TERRAIN_RAY_MIN_ABS_DZ:
                continue
            length, z_end = measure_terrain_descent(
                start=seed,
                outward=(dx, dy),
                z_peak=z_crest,
                z_at=lookup,
            )
            h = int(z_crest) - int(z_end)
            if length < 1 or h < TERRAIN_RAY_MIN_ABS_DZ:
                continue
            seen_seeds.add(seed)
            ref_cells.add((px, py))
            samples.append(
                SampleCell(seed, terrain_lo, relief_dz(z_crest, z_end), length),
            )
    samples.sort(key=lambda item: item.xy)
    return samples, ref_cells


def sample_landward_of_refs(
    shore_refs: list[tuple[Coord, int]],
    *,
    neighbor_site: NeighborSite,
    deltas: tuple[tuple[int, int], ...] = CARDINAL_ORTHO_DELTAS,
) -> tuple[list[SampleCell], set[Coord]]:
    """Deprecated v1: SHORE/abutment refs → landward ortho seeds.

    SoT: context plugin on the vertex body (R41), not per-ref ortho seeds.
    """
    samples: list[SampleCell] = []
    ref_cells: set[Coord] = set()
    seen_seeds: set[Coord] = set()

    for (lx, ly), shore_z in shore_refs:
        for dx, dy in deltas:
            seed = (lx + dx, ly + dy)
            if seed in seen_seeds:
                continue
            site = neighbor_site(seed)
            if site is None:
                continue
            terrain_lo, z_lo = site
            seen_seeds.add(seed)
            ref_cells.add((lx, ly))
            samples.append(SampleCell(seed, terrain_lo, relief_dz(shore_z, z_lo)))

    samples.sort(key=lambda item: item.xy)
    return samples, ref_cells
