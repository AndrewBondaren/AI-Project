"""Entry / scene ring geometry — WP-13 distance filters (shared slack formula)."""

from __future__ import annotations

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import (
    iter_meter_chunks,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import terrain_chunk_columns
from app.db.models.world import World


def chunk_center(rect: ColumnRect) -> tuple[float, float]:
    return (rect.x_min + rect.x_max) / 2.0, (rect.y_min + rect.y_max) / 2.0


def distance_sq(ax: float, ay: float, bx: float, by: float) -> float:
    return (ax - bx) ** 2 + (ay - by) ** 2


def tile_local_chunk_indices(
    rect: ColumnRect,
    meter_bbox: ColumnRect,
    chunk_size: int,
) -> tuple[int, int]:
    return (
        (rect.x_min - meter_bbox.x_min) // chunk_size,
        (rect.y_min - meter_bbox.y_min) // chunk_size,
    )


def ring_reach_m(radius_m: float, chunk_size: int) -> float:
    """Include chunk half-extent so edge chunks near the ring still match."""
    return float(radius_m) + float(chunk_size)


def chunk_within_ring(
    rect: ColumnRect,
    anchor_x: float,
    anchor_y: float,
    radius_m: float,
    chunk_size: int,
) -> bool:
    reach = ring_reach_m(radius_m, chunk_size)
    return distance_sq(*chunk_center(rect), anchor_x, anchor_y) <= reach * reach


def scene_chunk_indices(
    world: World,
    tile_gx: int,
    tile_gy: int,
    anchor_x: int,
    anchor_y: int,
    *,
    xy_radius: int,
) -> set[tuple[int, int]]:
    """Chunk (cx, cy) indices covered by scene volume around anchor."""
    cell_m = cell_size_m(world)
    chunk_size = terrain_chunk_columns(world)
    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    out: set[tuple[int, int]] = set()
    for rect in iter_meter_chunks(meter_bbox, chunk_size):
        if chunk_within_ring(rect, float(anchor_x), float(anchor_y), float(xy_radius), chunk_size):
            out.add(tile_local_chunk_indices(rect, meter_bbox, chunk_size))
    return out
