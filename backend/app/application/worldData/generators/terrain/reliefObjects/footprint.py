"""Shared mountain footprint — declare disk + autoresolve (coarse / light adapters)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from app.application.worldData.masks.mountainField import is_mountain_autoresolve
from app.dataModel.locations.enums.geographicSubtype import (
    GEOGRAPHIC_LOCATION_TYPE,
    GeographicSubtype,
)
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy

if TYPE_CHECKING:
    from app.db.models.namedLocation import NamedLocation

_DECLARE_SUBTYPES = frozenset({GeographicSubtype.MOUNTAIN, GeographicSubtype.PEAK})


def declare_radius_macro(declare_radius_light: int, light_side: int) -> int:
    """Light-cell declare radius → macro-tile disk radius."""
    side = max(1, int(light_side))
    return max(0, (max(0, int(declare_radius_light)) + side - 1) // side)


def iter_disk_cells(
    cx: int,
    cy: int,
    radius: int,
) -> Iterable[tuple[int, int]]:
    r = max(0, int(radius))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            yield cx + dx, cy + dy


def declare_mountain_locations(
    locations: list[NamedLocation],
) -> list[NamedLocation]:
    """Geographic mountain / peak anchors with map coords."""
    out: list[NamedLocation] = []
    for loc in locations:
        if loc.system_location_type != GEOGRAPHIC_LOCATION_TYPE:
            continue
        subtype = GeographicSubtype.from_wire(getattr(loc, "system_location_subtype", None))
        if subtype not in _DECLARE_SUBTYPES:
            continue
        if loc.map_x is None or loc.map_y is None:
            continue
        out.append(loc)
    return out


def declare_disk_keys(
    locations: list[NamedLocation],
    *,
    radius: int,
    xy_of: Callable[[NamedLocation], tuple[int, int]],
    accept: Callable[[tuple[int, int]], bool] | None = None,
) -> set[tuple[int, int]]:
    """Disk cells around declare anchors in caller coordinate space."""
    cells: set[tuple[int, int]] = set()
    for loc in declare_mountain_locations(locations):
        cx, cy = xy_of(loc)
        for key in iter_disk_cells(cx, cy, radius):
            if accept is not None and not accept(key):
                continue
            cells.add(key)
    return cells


def mountain_autoresolve_hit(
    *,
    seed: int,
    xm: int,
    ym: int,
    surface_z: int,
    typical_elevation_z: int,
    policy: MountainsCategoryPolicy,
) -> bool:
    """Thin wrapper — single SoT for coarse/light autoresolve gate."""
    return is_mountain_autoresolve(
        seed=seed,
        xm=xm,
        ym=ym,
        surface_z=surface_z,
        typical_elevation_z=typical_elevation_z,
        policy=policy,
    )
