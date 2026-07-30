"""Apply road_shoulder grade after road paint (R20–R28 data out).

Samples orthogonal neighbors → grade → expand by ``decision.width`` (RELIEF-T-16)
→ stamp ``system_facing``. ``structure_refs`` / ``earthen_canal`` stay on intents
(RELIEF-BAR-1 materialize).
"""

from __future__ import annotations

import logging

from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.facing import (
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    RoadShoulderGradeResult,
    RoadShoulderSegment,
    grade_road_shoulder_segments,
    segmentize_by_terrain,
)
from app.application.worldData.generators.terrain.relief.shoulderWidth import (
    expand_shoulder_ring,
    relief_dz,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import (
    light_cell_center_m,
    light_to_macro_local,
)
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import (
    RoadShoulderIntent,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy

logger = logging.getLogger(__name__)

_ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))


def apply_road_shoulder_grades(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    *,
    edge_uid: str,
    ordered_road_light: list[tuple[int, int]],
    road_cells: set[tuple[int, int]],
    object_policy: ObjectReliefPickPolicy | None = None,
    occurrence_start: int = 0,
) -> list[RoadShoulderIntent]:
    """Grade one edge's shoulders; mutate compose facing; append intents on ctx."""
    if not ordered_road_light or not ctx.relief_templates_by_uid:
        return []

    tile_set = set(ctx.tiles)
    samples = _sample_shoulder_cells(
        compose, ordered_road_light, road_cells, tile_set=tile_set,
    )
    if not samples:
        return []

    segments = segmentize_by_terrain(edge_uid=edge_uid, cells=samples)
    results = grade_road_shoulder_segments(
        world=ctx.world,
        world_seed=bake_seed(ctx.world),
        segments=segments,
        templates_by_uid=ctx.relief_templates_by_uid,
        object_policy=object_policy,
        occurrence_start=occurrence_start,
    )
    intents: list[RoadShoulderIntent] = []
    for result in results:
        if result.decision.skipped or result.decision.kind is None:
            intents.append(_to_intent(result, result.segment.cell_coords))
            continue
        expanded = expand_shoulder_ring(
            result.segment.cell_coords,
            road_cells,
            result.decision.width,
        )
        wide_coords = tuple(sorted(expanded))
        wide_segment = RoadShoulderSegment(
            edge_uid=result.segment.edge_uid,
            terrain_key=result.segment.terrain_key,
            system_terrain=result.segment.system_terrain,
            dz=result.segment.dz,
            site_id=result.segment.site_id,
            cell_coords=wide_coords,
        )
        wide_result = RoadShoulderGradeResult(
            segment=wide_segment,
            decision=result.decision,
            template_uid=result.template_uid,
        )
        _stamp_segment(
            compose,
            wide_result,
            road_cells=road_cells,
            tile_set=tile_set,
        )
        intents.append(_to_intent(wide_result, wide_coords))
    ctx.road_shoulder_intents.extend(intents)
    logger.debug(
        "relief | road_shoulder edge=%s segments=%d applied=%d",
        edge_uid,
        len(segments),
        sum(1 for i in intents if not i.skipped),
    )
    return intents


def _to_intent(
    result: RoadShoulderGradeResult,
    cell_coords: tuple[tuple[int, int], ...],
) -> RoadShoulderIntent:
    d = result.decision
    kind = d.kind.value if d.kind is not None else None
    return RoadShoulderIntent(
        edge_uid=result.segment.edge_uid,
        site_id=result.segment.site_id,
        template_uid=result.template_uid,
        kind=kind,
        width=d.width,
        cell_coords=cell_coords,
        earthen_canal=d.earthen_canal,
        structure_refs=d.structure_refs,
        skipped=d.skipped,
        reason=d.reason,
    )


def _sample_shoulder_cells(
    compose: LightGridCompose,
    ordered_road: list[tuple[int, int]],
    road_cells: set[tuple[int, int]],
    *,
    tile_set: set[tuple[int, int]],
) -> list[tuple[tuple[int, int], str, int]]:
    """Stable walk: for each road cell, emit orthogonal non-road neighbors once."""
    scale = compose.scale
    seen: set[tuple[int, int]] = set()
    out: list[tuple[tuple[int, int], str, int]] = []
    for lx, ly in ordered_road:
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        road_cell = compose.get(gx, gy, tx, ty)
        if road_cell is None:
            continue
        road_z = int(road_cell.surface_z)
        for dx, dy in _ORTHO:
            nx, ny = lx + dx, ly + dy
            if (nx, ny) in road_cells or (nx, ny) in seen:
                continue
            ngx, ngy, ntx, nty = light_to_macro_local(nx, ny, scale)
            if (ngx, ngy) not in tile_set:
                continue
            if not (0 <= ntx < scale.side and 0 <= nty < scale.side):
                continue
            neighbor = compose.get(ngx, ngy, ntx, nty)
            if neighbor is None or not neighbor.system_terrain:
                continue
            seen.add((nx, ny))
            out.append(((nx, ny), str(neighbor.system_terrain), relief_dz(road_z, neighbor.surface_z)))
    return out


def _stamp_segment(
    compose: LightGridCompose,
    result: RoadShoulderGradeResult,
    *,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> None:
    scale = compose.scale
    kind = result.decision.kind
    for lx, ly in result.segment.cell_coords:
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        cell = compose.get(gx, gy, tx, ty)
        if cell is None:
            continue
        if kind == ReliefSideKind.SHEER:
            cell.system_facing = None
            continue
        target = _nearest_road_center(compose, lx, ly, road_cells, tile_set)
        if target is None:
            continue
        cx, cy = light_cell_center_m(gx, gy, tx, ty, scale)
        facing = uphill_facing_toward(cx, cy, target[0], target[1])
        cell.system_facing = facing_wire(facing)


def _nearest_road_center(
    compose: LightGridCompose,
    lx: int,
    ly: int,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> tuple[float, float] | None:
    scale = compose.scale
    # Prefer ortho neighbor; else any road cell by manhattan (expanded ring)
    best: tuple[int, tuple[int, int]] | None = None
    for rx, ry in road_cells:
        dist = abs(rx - lx) + abs(ry - ly)
        if best is None or dist < best[0]:
            best = (dist, (rx, ry))
    if best is None:
        return None
    rx, ry = best[1]
    ngx, ngy, ntx, nty = light_to_macro_local(rx, ry, scale)
    if (ngx, ngy) not in tile_set:
        return None
    return light_cell_center_m(ngx, ngy, ntx, nty, scale)
