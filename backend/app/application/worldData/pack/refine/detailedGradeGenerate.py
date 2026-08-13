"""Outdoor grade generate on detailed_bake geometry — R36u / R36v."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.ribbonGrade import (
    RibbonGradeResult,
    grade_ribbon_segments,
)
from app.application.worldData.generators.terrain.relief.ribbonSegmentize import (
    segmentize_by_terrain,
)
from app.application.worldData.generators.terrain.relief.ribbonSiteSample import SampleCell
from app.application.worldData.gradeInstanceMerge import merge_grade_instances
from app.application.worldData.pack.refine.columnBounds import (
    ColumnBounds,
    rect_contains,
)
from app.application.worldData.pack.refine.detailedGradeMaterialize import (
    materialize_segment_meter,
    resolve_segment_uid,
)
from app.application.worldData.pack.refine.detailedGradeResult import DetailedGradeResult
from app.application.worldData.pack.refine.detailedGradeSample import (
    sample_open_land_meter,
    sample_shore_meter,
)
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
)
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


@dataclass(frozen=True, slots=True)
class DetailedGradeSeedBatch:
    context: ReliefContext
    samples: tuple[SampleCell, ...]
    ref_cells: frozenset[Coord]


@dataclass(frozen=True, slots=True)
class PlannedGradeSegment:
    context: ReliefContext
    result: RibbonGradeResult
    ref_cells: frozenset[Coord]
    grade_uid: str


def grade_halo_cells(templates: dict[str, ReliefTemplate]) -> int:
    """Max outward L from template POJO (root + cases). Min 1 for ortho halo."""
    halo = 1
    for tpl in templates.values():
        halo = max(halo, int(tpl.outward_length_cells()))
        for cond in tpl.conditions:
            for case in cond.cases:
                halo = max(halo, int(case.outward_length_cells()))
    return halo


def sample_detailed_grade_rect(
    world: World,
    surface_state: TileSurfaceState,
    rect: ColumnBounds,
    *,
    halo: int,
    existing_uids: dict[Coord, str] | None = None,
) -> list[DetailedGradeSeedBatch]:
    """Fine-edge seeds with ``seed ∈ rect``; halo is read-only (R36v)."""
    grid = MeterGradeSurface.from_tile_surface_state(
        surface_state, alias_heights=True,
    )
    if existing_uids:
        grid.grade_uid.update(existing_uids)
    road_key = terrain_masks(world).default_roads.system_terrain
    batches: list[DetailedGradeSeedBatch] = []
    for context, sample_fn in _CONTEXT_SAMPLES:
        samples, refs = sample_fn(
            grid, road_key=road_key, world=world, rect=rect, halo=halo,
        )
        if not samples:
            continue
        batches.append(
            DetailedGradeSeedBatch(
                context=context,
                samples=tuple(samples),
                ref_cells=frozenset(refs),
            ),
        )
    return batches


def merge_seed_batches(
    groups: list[list[DetailedGradeSeedBatch]],
) -> dict[ReliefContext, DetailedGradeSeedBatch]:
    merged: dict[ReliefContext, list[SampleCell]] = {}
    refs: dict[ReliefContext, set[Coord]] = {}
    seen: dict[ReliefContext, set[Coord]] = {}
    for group in groups:
        for batch in group:
            samples = merged.setdefault(batch.context, [])
            owned = seen.setdefault(batch.context, set())
            refs.setdefault(batch.context, set()).update(batch.ref_cells)
            for item in batch.samples:
                if item.xy in owned:
                    continue
                owned.add(item.xy)
                samples.append(item)
    return {
        context: DetailedGradeSeedBatch(
            context=context,
            samples=tuple(sorted(items, key=lambda row: row.xy)),
            ref_cells=frozenset(refs.get(context, ())),
        )
        for context, items in merged.items()
    }


def plan_detailed_grade(
    world: World,
    merged: dict[ReliefContext, DetailedGradeSeedBatch],
    *,
    relief_templates_by_uid: dict[str, ReliefTemplate],
    existing_uids: dict[Coord, str] | None = None,
    surface_state: TileSurfaceState | None = None,
) -> list[PlannedGradeSegment]:
    """Stitch seeds across rects → one segment / one planned grade (R36v)."""
    world_seed = bake_seed(world)
    grid = (
        MeterGradeSurface.from_tile_surface_state(
            surface_state, alias_heights=True,
        )
        if surface_state is not None
        else None
    )
    planned: list[PlannedGradeSegment] = []
    for context, batch in merged.items():
        if not batch.samples:
            continue
        segments = segmentize_by_terrain(
            owner_uid=context.value,
            cells=list(batch.samples),
        )
        results = grade_ribbon_segments(
            world=world,
            world_seed=world_seed,
            segments=segments,
            templates_by_uid=relief_templates_by_uid,
            context=context,
        )
        for result in results:
            seeds = result.segment.cell_coords
            if not seeds:
                continue
            uid = resolve_segment_uid(
                world_uid=world.world_uid,
                site_id=result.segment.site_id,
                seeds=seeds,
                surface=grid,
                existing_uids=existing_uids,
            )
            planned.append(
                PlannedGradeSegment(
                    context=context,
                    result=result,
                    ref_cells=batch.ref_cells,
                    grade_uid=uid,
                ),
            )
    logger.info(
        "detailed_grade_plan | world=%s segments=%d seeds=%d",
        world.world_uid,
        len(planned),
        sum(len(b.samples) for b in merged.values()),
    )
    return planned


def plan_grade_for_rects(
    world: World,
    surface_state: TileSurfaceState,
    rects: list[ColumnBounds],
    *,
    relief_templates_by_uid: dict[str, ReliefTemplate],
    existing_uids: dict[Coord, str] | None = None,
    groups: list[list[DetailedGradeSeedBatch]] | None = None,
) -> list[PlannedGradeSegment]:
    """Sample (unless ``groups``) → stitch → plan. Shared by runner and facade."""
    if not relief_templates_by_uid:
        return []
    if groups is None:
        halo = grade_halo_cells(relief_templates_by_uid)
        groups = [
            sample_detailed_grade_rect(
                world, surface_state, rect, halo=halo, existing_uids=existing_uids,
            )
            for rect in rects
        ]
    return plan_detailed_grade(
        world,
        merge_seed_batches(groups),
        relief_templates_by_uid=relief_templates_by_uid,
        existing_uids=existing_uids,
        surface_state=surface_state,
    )


def materialize_planned_for_rect(
    world: World,
    surface_state: TileSurfaceState,
    rect: ColumnBounds,
    planned: list[PlannedGradeSegment],
    *,
    existing_uids: dict[Coord, str] | None = None,
) -> DetailedGradeResult:
    """Stamp uid + instances for seeds owned by ``rect``."""
    grid = MeterGradeSurface.from_tile_surface_state(
        surface_state, alias_heights=True,
    )
    if existing_uids:
        grid.grade_uid.update(existing_uids)
    instances: list[ReliefGradeInstance] = []
    for item in planned:
        seeds = tuple(
            xy for xy in item.result.segment.cell_coords
            if rect_contains(rect, xy[0], xy[1])
        )
        if not seeds:
            continue
        instances.extend(
            materialize_segment_meter(
                grid,
                world,
                item.result,
                ref_cells=set(item.ref_cells),
                seeds=seeds,
                existing_uids=existing_uids,
                grade_uid=item.grade_uid,
            ),
        )
    wrote = {
        xy: uid for xy, uid in grid.grade_uid.items()
        if rect_contains(rect, xy[0], xy[1])
    }
    return DetailedGradeResult(
        surface_grade_uid=wrote,
        grade_instances=tuple(instances),
    )


def materialize_grade_for_rects(
    world: World,
    surface_state: TileSurfaceState,
    rects: list[ColumnBounds],
    planned: list[PlannedGradeSegment],
    *,
    existing_uids: dict[Coord, str] | None = None,
) -> DetailedGradeResult:
    """Materialize each rect; result bag is cells in those rects only."""
    parts: list[ReliefGradeInstance] = []
    uids: dict[Coord, str] = {}
    for rect in rects:
        part = materialize_planned_for_rect(
            world, surface_state, rect, planned, existing_uids=existing_uids,
        )
        uids.update(part.surface_grade_uid)
        parts.extend(part.grade_instances)
    return DetailedGradeResult(
        surface_grade_uid=uids,
        grade_instances=merge_grade_instances(parts),
    )


def generate_detailed_grade(
    world: World,
    surface_state: TileSurfaceState,
    *,
    relief_templates_by_uid: dict[str, ReliefTemplate],
    rects: list[ColumnBounds] | None = None,
    existing_uids: dict[Coord, str] | None = None,
) -> DetailedGradeResult:
    """Facade: same helpers as FineChunkRunner (tests / patch bounds)."""
    if not relief_templates_by_uid:
        logger.debug(
            "detailed_grade_skip | world=%s reason=no_templates",
            world.world_uid,
        )
        return DetailedGradeResult.empty()

    work_rects: list[ColumnBounds]
    if rects is None:
        from app.application.worldData.generators.terrain.types import ColumnRect

        bbox = surface_state.heightmap.bbox
        work_rects = [ColumnRect(bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max)]
    else:
        work_rects = rects
    planned = plan_grade_for_rects(
        world, surface_state, work_rects,
        relief_templates_by_uid=relief_templates_by_uid,
        existing_uids=existing_uids,
    )
    result = materialize_grade_for_rects(
        world, surface_state, work_rects, planned, existing_uids=existing_uids,
    )
    logger.info(
        "detailed_grade_done | world=%s cells=%d instances=%d",
        world.world_uid,
        len(result.surface_grade_uid),
        len(result.grade_instances),
    )
    return result
