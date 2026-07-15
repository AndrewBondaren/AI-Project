"""Macro tiles to fully materialize for world init / debug (not entire bbox)."""

from __future__ import annotations

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import macro_tile_of
from app.application.worldData.pack.bake.packTileCollect import (
    declared_hydro_tiles,
    location_anchor_tiles,
)
from app.dataModel.worldPack.packBakeDefaults import (
    PackBakeDefaults,
    resolve_light_tile_cap,
)
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
    defaults: PackBakeDefaults | None = None,
) -> list[Tile]:
    """
    Priority macro tiles for init testing: anchors → declared hydro → meter rivers → coarse flood.

    ``max_tiles``: ``None`` → ``defaults.max_tiles_light``; ``<= 0`` → no cap
    (via ``resolve_light_tile_cap``).
    """
    priority: dict[Tile, int] = {}

    def add(tile: Tile, tier: int) -> None:
        if tile not in priority or priority[tile] > tier:
            priority[tile] = tier

    for tile in location_anchor_tiles(world, locations):
        add(tile, 0)
    for tile in declared_hydro_tiles(world, locations):
        add(tile, 1)

    cell_m = cell_size_m(world)
    for xm, ym in (sparse_meter_hydro or {}):
        add(macro_tile_of(xm, ym, cell_m), 2)

    for gx, gy in coarse_hydro:
        add((gx, gy), 3)

    ordered = sorted(priority.keys(), key=lambda t: (priority[t], t[1], t[0]))
    cap = resolve_light_tile_cap(max_tiles, defaults=defaults)
    if cap is not None:
        ordered = ordered[:cap]
    return ordered
