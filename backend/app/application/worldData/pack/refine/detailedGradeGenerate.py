"""Outdoor grade generate on detailed_bake geometry — R36u single-writer facade."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.ribbonGrade import grade_ribbon_segments
from app.application.worldData.generators.terrain.relief.ribbonSegmentize import (
    segmentize_by_terrain,
)
from app.application.worldData.pack.refine.detailedGradeMaterialize import (
    materialize_segment_meter,
)
from app.application.worldData.pack.refine.detailedGradeResult import DetailedGradeResult
from app.application.worldData.pack.refine.detailedGradeSample import (
    sample_open_land_meter,
    sample_shore_meter,
)
from app.application.worldData.pack.refine.meterGradeSurface import MeterGradeSurface
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World

logger = logging.getLogger(__name__)

_CONTEXT_SAMPLES = (
    (ReliefContext.OPEN_LAND, sample_open_land_meter),
    (ReliefContext.SHORE, sample_shore_meter),
)


def generate_detailed_grade(
    world: World,
    surface_state: TileSurfaceState,
    *,
    relief_templates_by_uid: dict[str, ReliefTemplate],
) -> DetailedGradeResult:
    """Produce meter ``surface_grade_uid`` bag from tile surface (masks already carried)."""
    if not relief_templates_by_uid:
        logger.debug(
            "detailed_grade_skip | world=%s reason=no_templates",
            world.world_uid,
        )
        return DetailedGradeResult.empty()

    grid = MeterGradeSurface.from_tile_surface_state(surface_state)
    road_key = terrain_masks(world).default_roads.system_terrain
    world_seed = bake_seed(world)
    instances: list[ReliefGradeInstance] = []

    for context, sample_fn in _CONTEXT_SAMPLES:
        samples, ref_cells = sample_fn(grid, road_key=road_key, world=world)
        if not samples:
            continue
        segments = segmentize_by_terrain(
            owner_uid=context.value,
            cells=samples,
        )
        results = grade_ribbon_segments(
            world=world,
            world_seed=world_seed,
            segments=segments,
            templates_by_uid=relief_templates_by_uid,
            object_policy=None,
            occurrence_start=0,
            context=context,
        )
        for result in results:
            instances.extend(
                materialize_segment_meter(
                    grid,
                    world,
                    result,
                    ref_cells=ref_cells,
                ),
            )

    logger.info(
        "detailed_grade_done | world=%s cells=%d instances=%d",
        world.world_uid,
        len(grid.grade_uid),
        len(instances),
    )
    return DetailedGradeResult(
        surface_grade_uid=dict(grid.grade_uid),
        grade_instances=tuple(instances),
    )
