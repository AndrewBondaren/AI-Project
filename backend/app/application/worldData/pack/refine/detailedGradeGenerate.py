"""Outdoor grade generate on detailed_bake geometry — R36u / R36v.

Sample / ``plan_grade_for_rects`` / pre-pool occupancy are **deprecated v1**
(R38–R40). SoT discover is R41 (``.cursor/plans/relief-pipeline-v2.md``).
L2 ``materialize_*`` / catalog ``face_key`` are not deprecated.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.relief.geom.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.pick.ribbonGrade import (
    grade_ribbon_segments,
)
from app.application.worldData.generators.terrain.relief.sample.ribbonSegmentize import (
    segmentize_by_terrain,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.generators.terrain.relief.sample.ribbonSiteSample import SampleCell
from app.application.worldData.pack.refine.columnBounds import ColumnBounds, rect_contains
from app.application.worldData.pack.refine.detailedGradeCatalog import (
    TileFaceCatalog,
    catalog_for_surface,
)
from app.application.worldData.pack.refine.detailedGradeDiscover import discover_and_paint
from app.application.worldData.pack.refine.detailedGradeGraph import stitch_planned_segments
from app.application.worldData.pack.refine.detailedGradeHalo import grade_halo_cells
from app.application.worldData.pack.refine.detailedGradeMaterialize import (
    materialize_segment_meter,
)
from app.application.worldData.pack.refine.detailedGradePlan import (
    PlannedGradeSegment,
    split_mixed_outward,
)
from app.application.worldData.pack.refine.detailedGradeResult import DetailedGradeResult
from app.application.worldData.pack.refine.detailedGradeSample import (
    sample_open_land_meter,
    sample_ravine_meter,
    sample_road_shoulder_meter,
    sample_shore_meter,
)
from app.application.worldData.pack.refine.gridNeighborHalo import overlay_halo_from_surface
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
    apply_grade_uids,
)
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World

logger = logging.getLogger(__name__)

# Later stamp overwrites on a shared seed. Order = TZ priority
# (road_shoulder > shore > ravine > open_land); mountain Q4 later.
_CONTEXT_SAMPLES = (
    (ReliefContext.OPEN_LAND, sample_open_land_meter),
    (ReliefContext.RAVINE, sample_ravine_meter),
    (ReliefContext.SHORE, sample_shore_meter),
    (ReliefContext.ROAD_SHOULDER, sample_road_shoulder_meter),
)


@dataclass(frozen=True, slots=True)
class DetailedGradeSeedBatch:
    context: ReliefContext
    samples: tuple[SampleCell, ...]
    ref_cells: frozenset[Coord]


def sample_detailed_grade_rect(
    world: World,
    surface_state: TileSurfaceState,
    rect: ColumnBounds,
    *,
    halo: int,
    existing_uids: dict[Coord, str] | None = None,
    job_uid: str | None = None,
) -> list[DetailedGradeSeedBatch]:
    """Deprecated v1: fine-edge seeds with ``seed ∈ rect``; halo read-only (R36v).

    Not the live writer. ``compute_rect`` uses ``discover_and_paint`` (R41).
    """
    grid = MeterGradeSurface.from_tile_surface_state(
        surface_state, alias_heights=True,
    )
    if existing_uids:
        apply_grade_uids(grid, existing_uids)
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
    relief_debug(
        "detailed_grade_sample_rect",
        world_uid=world.world_uid,
        x_min=rect.x_min,
        x_max=rect.x_max,
        y_min=rect.y_min,
        y_max=rect.y_max,
        halo=halo,
        seeds=sum(len(b.samples) for b in batches),
        refs=sum(len(b.ref_cells) for b in batches),
        contexts=",".join(b.context.value for b in batches) or None,
        job_uid=job_uid,
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


def plan_rect_grade(
    world: World,
    batches: list[DetailedGradeSeedBatch],
    catalog: TileFaceCatalog,
    *,
    relief_templates_by_uid: dict[str, ReliefTemplate],
    surface_state: TileSurfaceState | None = None,
) -> list[PlannedGradeSegment]:
    """Deprecated v1: per-rect occupancy. Face uid is bound at stitch (C28).

    SoT: GradePaintSpec in the worker (R41). Mixed corridor outwards are split
    before interior numbering.
    """
    if not relief_templates_by_uid or not batches:
        return []
    world_seed = bake_seed(world)
    planned: list[PlannedGradeSegment] = []
    interior_by_chunk: dict[tuple[int, int], list[PlannedGradeSegment]] = {}
    for batch in batches:
        if not batch.samples:
            continue
        if batch.context is ReliefContext.OPEN_LAND:
            segments = []
            for item in batch.samples:
                segments.extend(
                    segmentize_by_terrain(
                        owner_uid=f"{batch.context.value}|{item.xy[0]},{item.xy[1]}",
                        cells=[item],
                    ),
                )
        else:
            segments = segmentize_by_terrain(
                owner_uid=batch.context.value,
                cells=list(batch.samples),
            )
        results = grade_ribbon_segments(
            world=world,
            world_seed=world_seed,
            segments=segments,
            templates_by_uid=relief_templates_by_uid,
            context=batch.context,
        )
        occupancy: list[PlannedGradeSegment] = []
        for result in results:
            if not result.segment.cell_coords:
                continue
            occupancy.extend(
                split_mixed_outward(
                    PlannedGradeSegment(
                        context=batch.context,
                        result=result,
                        ref_cells=batch.ref_cells,
                        grade_uid="",
                    ),
                ),
            )
        for item in occupancy:
            seeds = item.result.segment.cell_coords
            if catalog.faces_for_cells(seeds):
                planned.append(item)
                continue
            cx, cy = catalog.chunk_of(*min(seeds))
            interior_by_chunk.setdefault((cx, cy), []).append(item)
    for (cx, cy), items in interior_by_chunk.items():
        items.sort(key=lambda row: min(row.result.segment.cell_coords))
        for k, item in enumerate(items):
            planned.append(
                PlannedGradeSegment(
                    context=item.context,
                    result=item.result,
                    ref_cells=item.ref_cells,
                    grade_uid=catalog.interior_uid(cx, cy, k),
                ),
            )
    logger.info(
        "detailed_grade_plan | world=%s segments=%d tile_uid=%s",
        world.world_uid,
        len(planned),
        catalog.macro_tile_uid(),
    )
    return planned


def plan_grade_for_rects(
    world: World,
    surface_state: TileSurfaceState,
    rects: list[ColumnBounds],
    *,
    catalog: TileFaceCatalog,
    relief_templates_by_uid: dict[str, ReliefTemplate],
    existing_uids: dict[Coord, str] | None = None,
    groups: list[list[DetailedGradeSeedBatch]] | None = None,
) -> list[PlannedGradeSegment]:
    """Deprecated v1: sample each rect → occupancy → C28 stitch (face uid).

    SoT: discover in the ColumnRect worker (R41), not serial sample-all before
    the pool. Plan: ``.cursor/plans/relief-pipeline-v2.md``.
    """
    if not relief_templates_by_uid:
        return []
    halo = grade_halo_cells(relief_templates_by_uid)
    planned: list[PlannedGradeSegment] = []
    if groups is None:
        groups = [
            sample_detailed_grade_rect(
                world, surface_state, rect, halo=halo, existing_uids=existing_uids,
                job_uid=catalog.job_uid_chunk(*catalog.chunk_of_rect(rect)),
            )
            for rect in rects
        ]
    for batches in groups:
        planned.extend(
            plan_rect_grade(
                world, batches, catalog,
                relief_templates_by_uid=relief_templates_by_uid,
                surface_state=surface_state,
            ),
        )
    return stitch_planned_segments(catalog, planned)


def materialize_planned_for_rect(
    world: World,
    surface_state: TileSurfaceState,
    rect: ColumnBounds,
    planned: list[PlannedGradeSegment],
    *,
    existing_uids: dict[Coord, str] | None = None,
    catalog: TileFaceCatalog | None = None,
) -> DetailedGradeResult:
    """Uid + volume z overlay + instances for seeds owned by ``rect``.

    L2 apply is SoT (Post-R36w). The ``planned`` list is deprecated v1 occupancy;
    v2 feeds the same apply from ``GradePaintSpec``.
    """
    grid = MeterGradeSurface.from_tile_surface_state(
        surface_state, alias_heights=True,
    )
    if existing_uids:
        apply_grade_uids(grid, existing_uids)
    acc = DetailedGradeResult.empty()
    for item in planned:
        seeds = tuple(
            xy for xy in item.result.segment.cell_coords
            if rect_contains(rect, xy[0], xy[1])
        )
        if not seeds:
            continue
        part = materialize_segment_meter(
            grid,
            world,
            item.result,
            ref_cells=set(item.ref_cells),
            seeds=seeds,
            existing_uids=existing_uids,
            grade_uid=item.grade_uid,
            catalog=catalog,
        )
        acc = acc.merged_with(part)
        # Clearance bag for later seeds — full corridor, including outside rect.
        # Write-set membership is ``clipped`` below, not this stamp.
        apply_grade_uids(grid, part.surface_grade_uid)
    clipped = acc.clipped_to_rect(rect)
    relief_debug(
        "detailed_grade_materialize_rect",
        world_uid=world.world_uid,
        x_min=rect.x_min,
        x_max=rect.x_max,
        y_min=rect.y_min,
        y_max=rect.y_max,
        cells=len(clipped.surface_grade_uid),
        overlay=len(clipped.surface_z),
        instances=len(clipped.grade_instances),
        uids=len({inst.grade_uid for inst in clipped.grade_instances}),
    )
    return clipped


def materialize_grade_for_rects(
    world: World,
    surface_state: TileSurfaceState,
    rects: list[ColumnBounds],
    planned: list[PlannedGradeSegment],
    *,
    existing_uids: dict[Coord, str] | None = None,
    catalog: TileFaceCatalog | None = None,
) -> DetailedGradeResult:
    """Materialize each rect; result bag is cells in those rects only."""
    acc = DetailedGradeResult.empty()
    for rect in rects:
        acc = acc.merged_with(
            materialize_planned_for_rect(
                world, surface_state, rect, planned, existing_uids=existing_uids,
                catalog=catalog,
            ),
        )
    return acc


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

    Discover+paint per rect (R41). ``plan_grade_for_rects`` is deprecated v1.

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
