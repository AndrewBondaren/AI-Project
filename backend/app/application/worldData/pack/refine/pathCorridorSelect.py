"""Path corridor rect selection for PLAYER_PATH refine (MERGE-5 / DEBT-7).

Does not persist — returns ``ColumnRect`` list for ``FineChunkRunner``.
"""

from __future__ import annotations

from app.application.worldData.generators.coordinates import map_cell_fine_span
from app.application.worldData.generators.coordinates.worldTile import (
    iter_fine_chunks,
    fine_bbox_for_tile,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.pack.refine.pathHeading import (
    PathHeading,
    filter_corridor_rects,
)
from app.dataModel.worldPack.bake.pathHeadingPolicy import PathHeadingPolicy
from app.db.models.world import World


def select_path_corridor_rects(
    world: World,
    tile_gx: int,
    tile_gy: int,
    anchor_x: int,
    anchor_y: int,
    heading: PathHeading,
    *,
    depth_tiles: int | None = None,
) -> list[ColumnRect]:
    """Filter fine chunks in tile to heading corridor; empty if heading undefined."""
    if not heading.is_defined:
        return []
    tile_macro = map_cell_fine_span(world)
    chunk_size = terrain_chunk_columns(world)
    fine_bbox = fine_bbox_for_tile(tile_gx, tile_gy, tile_macro)
    rects = list(iter_fine_chunks(fine_bbox, chunk_size))
    depth = (
        depth_tiles
        if depth_tiles is not None
        else PathHeadingPolicy.canonical_defaults().path_ahead_depth
    )
    depth_fine = float(depth * tile_macro)
    heading_policy = PathHeadingPolicy.canonical_defaults()
    return filter_corridor_rects(
        rects,
        float(anchor_x),
        float(anchor_y),
        heading,
        depth_fine=depth_fine,
        half_width_fine=heading_policy.corridor_half_width_fine(chunk_size),
    )
