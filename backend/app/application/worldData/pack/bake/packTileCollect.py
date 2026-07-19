"""Shared L0 macro-tile collectors for light/full bake planning (WP-27).

Master contract (2026-07-19): light = location tiles ∪ declared hydro;
full = entire world_bounds. ``bootstrap_macro_tiles`` — debug priority preview only.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import (
    iter_macro_tiles,
    macro_tile_of,
)
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

Tile = tuple[int, int]


def _sorted_tiles(tiles: Iterable[Tile]) -> list[Tile]:
    return sorted(tiles, key=lambda t: (t[1], t[0]))


def location_anchor_tiles(
    world: World,
    locations: list[NamedLocation],
) -> set[Tile]:
    cell_m = cell_size_m(world)
    return {
        macro_tile_of(loc.map_x, loc.map_y, cell_m)
        for loc in static_map_anchors(locations)
    }


def declared_hydro_tiles(
    world: World,
    locations: list[NamedLocation],
) -> set[Tile]:
    """Macro-tiles covering declared coastline / lake shore / river endpoints."""
    if not is_hydrology_enabled(world):
        return set()
    cell_m = cell_size_m(world)
    tiles: set[Tile] = set()
    loaded = load_declared_hydrology(world, locations)
    for a, b in loaded.coastline_segments:
        tiles.add(macro_tile_of(a[0], a[1], cell_m))
        tiles.add(macro_tile_of(b[0], b[1], cell_m))
    for lake in loaded.lake_specs:
        for a, b in lake.shoreline_segments:
            tiles.add(macro_tile_of(a[0], a[1], cell_m))
            tiles.add(macro_tile_of(b[0], b[1], cell_m))
    for edge in loaded.river_edges:
        a, b = edge.segment
        tiles.add(macro_tile_of(a[0], a[1], cell_m))
        tiles.add(macro_tile_of(b[0], b[1], cell_m))
    return tiles


def light_l0_tiles(
    world: World,
    locations: list[NamedLocation],
) -> list[Tile]:
    """Light L0 set: named_location tiles ∪ declared hydro — no cap, no coarse flood."""
    return _sorted_tiles(
        location_anchor_tiles(world, locations) | declared_hydro_tiles(world, locations),
    )


def world_bounds_l0_tiles(
    world: World,
    locations: list[NamedLocation],
) -> list[Tile]:
    """Full L0 set: every macro-tile covering resolved ``world_bounds`` / v1 AABB."""
    bbox = grid_bbox_from_locations(world, locations)
    if bbox is None:
        return []
    return _sorted_tiles(iter_macro_tiles(bbox))
