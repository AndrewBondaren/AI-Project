"""Background chunk enqueue — rings and path-ahead (WP-13 / WP-PERF-10).

Does not write pack blobs or generate cells — only ``ChunkRefineQueue``.
"""

from __future__ import annotations

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import (
    iter_meter_chunks,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.pack.bake.packBakeLog import log_pack_queue_scheduled
from app.application.worldData.pack.refine.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.entryRingGeom import (
    chunk_within_ring,
    tile_local_chunk_indices,
)
from app.application.worldData.pack.refine.pathHeading import (
    PathHeading,
    macro_tiles_ahead,
    predicted_border_entry,
)
from app.application.worldData.pack.read.packMapHelpers import world_tile_size_m
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.db.models.world import World


async def schedule_tile_background(
    world: World,
    queue: ChunkRefineQueue,
    anchor_x: int,
    anchor_y: int,
    tile_gx: int,
    tile_gy: int,
    *,
    skip_scene_rects: set[tuple[int, int]] | None = None,
    max_radius_m: float | None = None,
) -> int:
    """Enqueue background chunks near anchor — WP-13 rings, not whole tile (WP-PERF-10)."""
    cell_m = cell_size_m(world)
    chunk_size = terrain_chunk_columns(world)
    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    skip = skip_scene_rects or set()
    policy = SceneVolumePolicy.canonical_defaults()
    radius = (
        float(max_radius_m)
        if max_radius_m is not None
        else float(policy.background_expand_radius_m)
    )
    count = 0
    for rect in iter_meter_chunks(meter_bbox, chunk_size):
        cx, cy = tile_local_chunk_indices(rect, meter_bbox, chunk_size)
        if (cx, cy) in skip:
            continue
        if not chunk_within_ring(rect, float(anchor_x), float(anchor_y), radius, chunk_size):
            continue
        if queue.enqueue_chunk(
            tile_gx, tile_gy, cx, cy,
            anchor_x=float(anchor_x),
            anchor_y=float(anchor_y),
            chunk_columns=chunk_size,
            tile_size_m=cell_m,
        ):
            count += 1
    if count:
        log_pack_queue_scheduled(
            world.world_uid,
            f"tile_background gx={tile_gx} gy={tile_gy} r<={radius:.0f}m",
            enqueued=count,
            queue_depth=len(queue),
        )
    return count


async def schedule_path_ahead_tiles(
    world: World,
    queue: ChunkRefineQueue,
    anchor_x: int,
    anchor_y: int,
    tile_gx: int,
    tile_gy: int,
    heading: PathHeading,
    *,
    depth_tiles: int,
) -> int:
    """Enqueue background rings on macro-tiles ahead (WP-17).

    Each neighbor tile uses **predicted border entry** as ring anchor (WP-13),
    not the current spawn/session anchor.
    """
    tile_size = world_tile_size_m(world)
    count = 0
    prev_gx, prev_gy = tile_gx, tile_gy
    for ngx, ngy in macro_tiles_ahead(tile_gx, tile_gy, heading, depth_tiles):
        entry_x, entry_y = predicted_border_entry(
            prev_gx, prev_gy, ngx, ngy,
            float(anchor_x), float(anchor_y),
            tile_size,
        )
        count += await schedule_tile_background(
            world, queue, entry_x, entry_y, ngx, ngy,
        )
        prev_gx, prev_gy = ngx, ngy
    if count:
        log_pack_queue_scheduled(
            world.world_uid,
            f"path_ahead depth={depth_tiles}",
            enqueued=count,
            queue_depth=len(queue),
        )
    return count
