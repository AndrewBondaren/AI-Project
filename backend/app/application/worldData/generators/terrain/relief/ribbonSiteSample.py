"""Shared ribbon site sample — R36u-T-7 (meter + leftover L0)."""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from app.application.worldData.generators.terrain.relief.facing import CARDINAL_ORTHO_DELTAS
from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz

Coord = tuple[int, int]
NeighborSite = Callable[[Coord], tuple[str, int] | None]


class SampleCell(NamedTuple):
    """One ribbon seed: downhill/landward cell + terrain + measured Δz."""

    xy: Coord
    terrain: str
    dz: int


def sample_downhill_land_sites(
    land: dict[Coord, tuple[str, int]],
    *,
    deltas: tuple[tuple[int, int], ...] = CARDINAL_ORTHO_DELTAS,
) -> tuple[list[SampleCell], set[Coord]]:
    """Uphill land = ref; downhill ortho neighbor = seed."""
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


def sample_landward_of_refs(
    shore_refs: list[tuple[Coord, int]],
    *,
    neighbor_site: NeighborSite,
    deltas: tuple[tuple[int, int], ...] = CARDINAL_ORTHO_DELTAS,
) -> tuple[list[SampleCell], set[Coord]]:
    """SHORE/abutment refs → landward ortho seeds via adapter ``neighbor_site``."""
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
