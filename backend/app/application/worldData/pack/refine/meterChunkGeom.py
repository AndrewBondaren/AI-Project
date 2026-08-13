"""Shared meter-chunk geometry for pack L2 refine / detailed bake.

Grid math only — no I/O, no generate. Callers: PackDetailedBake, FineTerrainRefine.
"""

from __future__ import annotations

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import (
    iter_meter_chunks,
    macro_tile_of,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.pack.refine.columnBounds import (
    expand_rect,
    rect_contains as bounds_contains,
)
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.db.models.world import World


def rect_contains(rect: ColumnRect, x: int, y: int) -> bool:
    return bounds_contains(rect, x, y)


def expand_column_rect(rect: ColumnRect, halo: int) -> ColumnRect:
    expanded = expand_rect(rect, halo)
    if expanded is rect:
        return rect
    return ColumnRect(
        x_min=expanded.x_min,
        x_max=expanded.x_max,
        y_min=expanded.y_min,
        y_max=expanded.y_max,
    )


def _rect_overlaps_volume(rect: ColumnRect, volume: TerritoryVolume) -> bool:
    return not (
        rect.x_max < volume.x0
        or rect.x_min > volume.x1
        or rect.y_max < volume.y0
        or rect.y_min > volume.y1
    )


def tiles_covering_volume(world: World, volume: TerritoryVolume) -> list[tuple[int, int]]:
    cell_m = cell_size_m(world)
    corners = (
        (volume.x0, volume.y0),
        (volume.x0, volume.y1),
        (volume.x1, volume.y0),
        (volume.x1, volume.y1),
    )
    tiles = {macro_tile_of(x, y, cell_m) for x, y in corners}
    gxs = [g for g, _ in tiles]
    gys = [g for _, g in tiles]
    out: list[tuple[int, int]] = []
    for gy in range(min(gys), max(gys) + 1):
        for gx in range(min(gxs), max(gxs) + 1):
            out.append((gx, gy))
    return out


def rects_for_macro_tile(world: World, tile_gx: int, tile_gy: int) -> list[ColumnRect]:
    cell_m = cell_size_m(world)
    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    chunk_size = terrain_chunk_columns(world)
    return list(iter_meter_chunks(meter_bbox, chunk_size))


def expected_meter_chunks(world: World, tile_gx: int, tile_gy: int) -> int:
    return len(rects_for_macro_tile(world, tile_gx, tile_gy))


def rects_overlapping_volume(
    world: World,
    volume: TerritoryVolume,
    tile_gx: int,
    tile_gy: int,
) -> list[ColumnRect]:
    return [
        rect
        for rect in rects_for_macro_tile(world, tile_gx, tile_gy)
        if _rect_overlaps_volume(rect, volume)
    ]
