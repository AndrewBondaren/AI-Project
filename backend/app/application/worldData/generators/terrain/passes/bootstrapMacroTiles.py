"""Macro tiles to fully materialize for world init / debug (not entire bbox)."""

from __future__ import annotations

from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import macro_tile_of
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

Tile = tuple[int, int]


def bootstrap_macro_tiles(
    world: World,
    locations: list[NamedLocation],
    coarse_hydro: dict[Tile, object],
    sparse_meter_hydro: dict[Tile, object] | None,
    *,
    max_tiles: int | None = None,
) -> list[Tile]:
    """
    Priority macro tiles for init testing: anchors → declared hydro → meter rivers → coarse flood.

    ``max_tiles``: ``None`` → ``PackBakeDefaults.max_tiles_light``; ``<= 0`` → no cap.
    """
    cell_m = cell_size_m(world)
    priority: dict[Tile, int] = {}

    def add(tile: Tile, tier: int) -> None:
        if tile not in priority or priority[tile] > tier:
            priority[tile] = tier

    for loc in static_map_anchors(locations):
        add(macro_tile_of(loc.map_x, loc.map_y, cell_m), 0)

    if is_hydrology_enabled(world):
        loaded = load_declared_hydrology(world, locations)
        for a, b in loaded.coastline_segments:
            add(macro_tile_of(a[0], a[1], cell_m), 1)
            add(macro_tile_of(b[0], b[1], cell_m), 1)
        for lake in loaded.lake_specs:
            for a, b in lake.shoreline_segments:
                add(macro_tile_of(a[0], a[1], cell_m), 1)
                add(macro_tile_of(b[0], b[1], cell_m), 1)
        for edge in loaded.river_edges:
            a, b = edge.segment
            add(macro_tile_of(a[0], a[1], cell_m), 1)
            add(macro_tile_of(b[0], b[1], cell_m), 1)

    for xm, ym in (sparse_meter_hydro or {}):
        add(macro_tile_of(xm, ym, cell_m), 2)

    for gx, gy in coarse_hydro:
        add((gx, gy), 3)

    ordered = sorted(priority.keys(), key=lambda t: (priority[t], t[1], t[0]))
    cap = (
        PackBakeDefaults.canonical_defaults().max_tiles_light
        if max_tiles is None
        else max_tiles
    )
    if cap > 0:
        ordered = ordered[:cap]
    return ordered
