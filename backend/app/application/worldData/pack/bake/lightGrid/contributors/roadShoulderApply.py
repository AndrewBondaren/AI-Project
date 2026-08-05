"""Apply road_shoulder grade after road paint (R20–R28 / R36 §8b–§9 / §8c).

Phases per seed: clearance → edgeRoadAnchor → volume plan → stamp → Grade.
``structure_refs`` / ``earthen_canal`` stay on intents (RELIEF-BAR-1).
Dilate sample = Q6 (open).
"""

from __future__ import annotations

import logging

from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.edgeRoadAnchor import (
    EdgeRoadAnchor,
    edge_road_abutment,
)
from app.application.worldData.generators.terrain.relief.facing import (
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.geomResolve import ResolvedGeom
from app.application.worldData.generators.terrain.relief.gradeInstanceFactory import (
    build_ribbon_grade_instance,
)
from app.application.worldData.generators.terrain.relief.gradeObstacleLight import (
    is_grade_obstacle_light,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_warning
from app.application.worldData.generators.terrain.relief.ribbonSeedResolve import (
    SeedClearance,
    SeedClearanceSkip,
    resolve_seed_clearance,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    RoadShoulderGradeResult,
    grade_road_shoulder_segments,
    segmentize_by_terrain,
)
from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    RibbonVolumePlan,
    geom_for_cleared_length,
    plan_ribbon_volume,
    ribbon_sign_from_dz,
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
from app.dataModel.spatial.facing import opposite
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
    """Grade one edge's shoulders; mutate compose z/facing; append intents."""
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
        stamped, width_used = _materialize_segment(
            compose,
            ctx,
            result,
            road_cells=road_cells,
            tile_set=tile_set,
        )
        if not stamped:
            intents.append(
                _to_intent(
                    result,
                    (),
                    skipped=True,
                    reason="clearance_skip",
                    width=0,
                )
            )
            continue
        intents.append(_to_intent(result, stamped, width=width_used))
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
    *,
    skipped: bool | None = None,
    reason: str | None = None,
    width: int | None = None,
) -> RoadShoulderIntent:
    d = result.decision
    kind = d.kind.value if d.kind is not None else None
    return RoadShoulderIntent(
        edge_uid=result.segment.edge_uid,
        site_id=result.segment.site_id,
        template_uid=result.template_uid,
        kind=kind,
        width=d.requested_length if width is None else int(width),
        cell_coords=cell_coords,
        earthen_canal=d.earthen_canal,
        structure_refs=d.structure_refs,
        skipped=d.skipped if skipped is None else skipped,
        reason=d.reason if reason is None else reason,
    )


def _materialize_segment(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    result: RoadShoulderGradeResult,
    *,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> tuple[tuple[tuple[int, int], ...], int]:
    """Orchestrate per-seed phases; no inline clearance/geom/stamp logic."""
    kind = result.decision.kind
    assert kind is not None
    h = int(result.decision.h)
    if h < 1:
        return (), 0
    sign = ribbon_sign_from_dz(int(result.segment.dz))
    requested = max(0, int(result.decision.requested_length))
    stamped: list[tuple[int, int]] = []
    max_L = 0

    for seed in result.segment.cell_coords:
        clearance = resolve_seed_clearance(
            seed=seed,
            road_cells=road_cells,
            requested_length=requested,
            world=ctx.world,
            cell_blocked=lambda c: _cell_blocked_light(
                compose, c, tile_set=tile_set,
            ),
        )
        if isinstance(clearance, SeedClearanceSkip):
            relief_warning(
                "road_shoulder_skip",
                site_id=result.segment.site_id,
                why=clearance.why,
                seed=clearance.seed,
                free_gap=clearance.free_gap,
                requested=clearance.requested,
                L_eff=clearance.L_eff,
            )
            continue

        anchor = _resolve_edge_road_anchor(
            compose, clearance, road_cells=road_cells, tile_set=tile_set,
        )
        if anchor is None:
            relief_warning(
                "road_shoulder_skip",
                site_id=result.segment.site_id,
                why="no_edge_road_anchor",
                seed=seed,
            )
            continue

        plan = _plan_seed_volume(
            decision_geom=result.decision.geom,
            h=h,
            kind=kind,
            L_eff=clearance.L_eff,
            z_road=anchor.z,
            sign=sign,
        )
        if plan is None or not plan.columns:
            continue

        wrote = _stamp_ribbon_plan(
            compose,
            seed=seed,
            plan=plan,
            kind=kind,
            sign=sign,
            anchor=anchor,
            road_cells=road_cells,
            tile_set=tile_set,
        )
        if wrote:
            facing = _first_column_facing(
                compose, wrote[0], tile_set=tile_set,
            )
            grade = build_ribbon_grade_instance(
                world_uid=ctx.world.world_uid,
                site_id=result.segment.site_id,
                seed=seed,
                plan=plan,
                cell_refs=tuple(wrote),
                facing=facing,
                earthen_canal=result.decision.earthen_canal,
                template_uid=result.template_uid,
                edge_uid=result.segment.edge_uid,
            )
            _stamp_grade_uid(
                compose, wrote, grade.grade_uid, tile_set=tile_set,
            )
            ctx.relief_grade_instances.append(grade)
        stamped.extend(wrote)
        max_L = max(max_L, len(wrote))

    return tuple(sorted(set(stamped))), max_L


def _plan_seed_volume(
    *,
    decision_geom: ResolvedGeom | None,
    h: int,
    kind: ReliefSideKind,
    L_eff: int,
    z_road: int,
    sign: int,
) -> RibbonVolumePlan | None:
    """Phase: geom after clearance + volume columns."""
    if (
        decision_geom is not None
        and decision_geom.kind is kind
        and int(decision_geom.L) == int(L_eff)
        and int(decision_geom.h) == int(h)
    ):
        geom = decision_geom
    else:
        geom = geom_for_cleared_length(h=h, kind=kind, length=L_eff)
    if geom.L < 1:
        return None
    return plan_ribbon_volume(z_road=z_road, h=h, sign=sign, geom=geom)


def _resolve_edge_road_anchor(
    compose: LightGridCompose,
    clearance: SeedClearance,
    *,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> EdgeRoadAnchor | None:
    """Phase: footprint-edge abutment (seed − outward)."""
    abutment = edge_road_abutment(
        clearance.seed, clearance.outward, road_cells,
    )
    if abutment is None:
        return None
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(abutment[0], abutment[1], scale)
    if (gx, gy) not in tile_set:
        return None
    cell = compose.get(gx, gy, tx, ty)
    if cell is None:
        return None
    return EdgeRoadAnchor(
        xy=abutment,
        outward=clearance.outward,
        z=int(cell.surface_z),
        center_m=light_cell_center_m(gx, gy, tx, ty, scale),
    )


def _stamp_ribbon_plan(
    compose: LightGridCompose,
    *,
    seed: tuple[int, int],
    plan: RibbonVolumePlan,
    kind: ReliefSideKind,
    sign: int,
    anchor: EdgeRoadAnchor,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Phase: write surface_z + facing along outward from seed."""
    dx, dy = anchor.outward
    sx, sy = seed
    wrote: list[tuple[int, int]] = []
    for col in plan.columns:
        lx = sx + dx * (col.k - 1)
        ly = sy + dy * (col.k - 1)
        cell_xy = (lx, ly)
        if _is_obstacle(
            compose, cell_xy, road_cells=road_cells, tile_set=tile_set,
        ):
            break
        if not _stamp_column(
            compose,
            lx,
            ly,
            surface_z=col.surface_z,
            kind=kind,
            sign=sign,
            anchor=anchor,
            tile_set=tile_set,
        ):
            break
        wrote.append(cell_xy)
    return wrote


def _stamp_grade_uid(
    compose: LightGridCompose,
    cells: list[tuple[int, int]],
    grade_uid: str,
    *,
    tile_set: set[tuple[int, int]],
) -> None:
    scale = compose.scale
    for lx, ly in cells:
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        cell = compose.get(gx, gy, tx, ty)
        if cell is not None:
            cell.system_grade_uid = grade_uid


def _first_column_facing(
    compose: LightGridCompose,
    cell_xy: tuple[int, int],
    *,
    tile_set: set[tuple[int, int]],
) -> str | None:
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(cell_xy[0], cell_xy[1], scale)
    if (gx, gy) not in tile_set:
        return None
    cell = compose.get(gx, gy, tx, ty)
    if cell is None:
        return None
    return cell.system_facing


def _stamp_column(
    compose: LightGridCompose,
    lx: int,
    ly: int,
    *,
    surface_z: int,
    kind: ReliefSideKind,
    sign: int,
    anchor: EdgeRoadAnchor,
    tile_set: set[tuple[int, int]],
) -> bool:
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
    if (gx, gy) not in tile_set:
        return False
    cell = compose.get(gx, gy, tx, ty)
    if cell is None:
        return False
    cell.surface_z = int(surface_z)
    if kind is ReliefSideKind.SHEER:
        cell.system_facing = None
        return True
    cx, cy = light_cell_center_m(gx, gy, tx, ty, scale)
    toward_road = uphill_facing_toward(cx, cy, anchor.center_m[0], anchor.center_m[1])
    if toward_road is None:
        cell.system_facing = None
        return True
    facing = toward_road if sign < 0 else opposite(toward_road)
    cell.system_facing = facing_wire(facing)
    return True


def _cell_blocked_light(
    compose: LightGridCompose,
    cell: tuple[int, int],
    *,
    tile_set: set[tuple[int, int]],
) -> bool:
    """Bake adapter: OOB / missing / settlement pin (not road — see obstacle helper)."""
    lx, ly = cell
    scale = compose.scale
    gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
    if (gx, gy) not in tile_set:
        return True
    if not (0 <= tx < scale.side and 0 <= ty < scale.side):
        return True
    grid_cell = compose.get(gx, gy, tx, ty)
    if grid_cell is None:
        return True
    return grid_cell.location_pin is not None


def _is_obstacle(
    compose: LightGridCompose,
    cell: tuple[int, int],
    *,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
) -> bool:
    return is_grade_obstacle_light(
        cell,
        road_cells=road_cells,
        cell_blocked=lambda c: _cell_blocked_light(compose, c, tile_set=tile_set),
    )


def _sample_shoulder_cells(
    compose: LightGridCompose,
    ordered_road: list[tuple[int, int]],
    road_cells: set[tuple[int, int]],
    *,
    tile_set: set[tuple[int, int]],
) -> list[tuple[tuple[int, int], str, int]]:
    """Stable walk: for each road cell, emit orthogonal non-road neighbors once.

    Q6: still walks ``ordered`` (centerline), not dilated footprint edge.
    """
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
