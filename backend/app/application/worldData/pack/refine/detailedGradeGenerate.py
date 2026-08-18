"""Outdoor grade generate on detailed_bake geometry — R41 facade.

Same helpers as FineChunkRunner (tests / patch bounds). Discover+paint per
rect; catalog ``face_key`` and L2 apply are not occupancy.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.application.worldData.pack.refine.columnBounds import ColumnBounds
from app.application.worldData.pack.refine.detailedGradeCatalog import catalog_for_surface
from app.application.worldData.pack.refine.detailedGradeDiscover import discover_and_paint
from app.application.worldData.pack.refine.detailedGradeHalo import grade_halo_cells
from app.application.worldData.pack.refine.detailedGradeResult import DetailedGradeResult
from app.application.worldData.pack.refine.gridNeighborHalo import overlay_halo_from_surface
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World

logger = logging.getLogger(__name__)


def generate_detailed_grade(
    world: World,
    surface_state: TileSurfaceState,
    *,
    tile_gx: int,
    tile_gy: int,
    relief_templates_by_uid: dict[str, ReliefTemplate],
    rects: list[ColumnBounds] | None = None,
    existing_uids: dict[Coord, str] | None = None,
    chunk_size: int | None = None,
    halo_neighbors: Sequence[TileSurfaceState] | None = None,
) -> DetailedGradeResult:
    """Facade: same helpers as FineChunkRunner (tests / patch bounds).

    ``halo_neighbors`` — already-built neighbor ``TileSurfaceState`` (grid-adjacent
    meters). Same overlay as the runner's pack IO path; bbox of this tile is not
    expanded.
    """
    if not relief_templates_by_uid:
        logger.debug(
            "detailed_grade_skip | world=%s reason=no_templates",
            world.world_uid,
        )
        return DetailedGradeResult.empty()

    work_rects: list[ColumnBounds]
    bbox = surface_state.heightmap.bbox
    if rects is None:
        from app.application.worldData.generators.terrain.types import ColumnRect

        work_rects = [ColumnRect(bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max)]
    else:
        work_rects = rects
    if halo_neighbors:
        halo = grade_halo_cells(relief_templates_by_uid)
        for neighbor in halo_neighbors:
            surface_state = overlay_halo_from_surface(
                surface_state, neighbor, this_bbox=bbox, halo=halo,
            )
    catalog = catalog_for_surface(
        world, surface_state.heightmap.bbox,
        tile_gx=tile_gx, tile_gy=tile_gy, chunk_size=chunk_size,
    )
    halo = grade_halo_cells(relief_templates_by_uid)
    acc = DetailedGradeResult.empty()
    known = dict(existing_uids or {})
    for rect in work_rects:
        part, _seams = discover_and_paint(
            world, surface_state, rect,
            halo=halo,
            catalog=catalog,
            templates=relief_templates_by_uid,
            existing_uids=known,
        )
        acc = acc.merged_with(part)
        known.update(part.surface_grade_uid)
    logger.info(
        "detailed_grade_done | world=%s cells=%d overlay=%d instances=%d",
        world.world_uid,
        len(acc.surface_grade_uid),
        len(acc.surface_z),
        len(acc.grade_instances),
    )
    return acc
