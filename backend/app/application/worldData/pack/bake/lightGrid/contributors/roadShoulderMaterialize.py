"""Materialize road_shoulder segment seeds — bake (T-30/T-52 phases 0–1).

Per seed: clearance → canal → anchor → volume → stamp → Grade.
Adapters: ``roadShoulderAdapters`` (T-61).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.canalAttachments import (
    knobs_extra_structure_refs,
    project_canal_draw,
)
from app.application.worldData.generators.terrain.relief.gradeInstanceFactory import (
    build_ribbon_grade_instance,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RIBBON_SKIP,
    WHY_EMPTY_PLAN,
    WHY_EMPTY_STAMP,
    WHY_H_LT_1,
    WHY_NO_EDGE_ROAD_ANCHOR,
    WHY_NOT_STAMPED,
)
from app.application.worldData.generators.terrain.relief.reliefLog import (
    relief_debug,
    relief_warning,
)
from app.application.worldData.generators.terrain.relief.ribbonSeedResolve import (
    SeedClearanceSkip,
    resolve_seed_clearance,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    RoadShoulderGradeResult,
)
from app.application.worldData.generators.terrain.relief.seedCanalResolve import (
    aggregate_canals,
    resolve_seed_canal,
)
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    ribbon_sign_from_dz,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderAdapters import (
    plan_seed_volume,
    resolve_edge_road_anchor,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderStamp import (
    cell_blocked_light,
    first_column_facing,
    stamp_grade_uid,
    stamp_ribbon_plan,
)
from app.dataModel.terrain.relief.canal import Canal
from app.dataModel.terrain.relief.canalObstaclePolicy import CanalObstaclePolicyRule
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.worldCanalTemplateRegistry import (
    WorldCanalTemplateRegistry,
)


@dataclass(frozen=True, slots=True)
class SeedStampResult:
    """One successfully stamped seed strip (phase 0 contract)."""

    wrote: tuple[tuple[int, int], ...]
    canal: Canal | None


@dataclass(frozen=True, slots=True)
class SeedMaterializeSkip:
    """Seed did not stamp — why for Intent reason (RELIEF-T-64)."""

    why: str


@dataclass(frozen=True, slots=True)
class SegmentMaterializeResult:
    """Segment after all seeds (phase 0 contract)."""

    stamped: tuple[tuple[int, int], ...]
    width_used: int
    canal: Canal | None
    extra_structure_refs: tuple[str, ...]
    skip_why: str | None = None


def _aggregate_skip_why(whys: list[str]) -> str:
    if not whys:
        return WHY_NOT_STAMPED
    uniq = list(dict.fromkeys(whys))
    if len(uniq) == 1:
        return uniq[0]
    return WHY_NOT_STAMPED


def materialize_segment(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    result: RoadShoulderGradeResult,
    *,
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
    canal_registry: WorldCanalTemplateRegistry,
    canal_rules: Sequence[CanalObstaclePolicyRule],
) -> SegmentMaterializeResult:
    """Thin segment loop over ``materialize_seed``."""
    kind = result.decision.kind
    assert kind is not None
    h = int(result.decision.h)
    requested = max(0, int(result.decision.requested_length))
    d = result.decision
    extras = knobs_extra_structure_refs(
        earthen_canal=d.earthen_canal,
        structure_canal=d.structure_canal,
        structure_refs=d.structure_refs,
    )
    if h < 1:
        relief_debug(
            EVENT_RIBBON_SKIP,
            site_id=result.segment.site_id,
            why=WHY_H_LT_1,
            h=h,
        )
        return SegmentMaterializeResult(
            (), 0, None, extras, skip_why=WHY_H_LT_1,
        )

    sign = ribbon_sign_from_dz(int(result.segment.dz))
    stamped: list[tuple[int, int]] = []
    max_L = 0
    stamped_canals: list[Canal] = []
    skip_whys: list[str] = []

    for seed in result.segment.cell_coords:
        seed_out = materialize_seed(
            compose,
            ctx,
            result,
            seed=seed,
            requested=requested,
            h=h,
            kind=kind,
            sign=sign,
            extras=extras,
            road_cells=road_cells,
            tile_set=tile_set,
            canal_registry=canal_registry,
            canal_rules=canal_rules,
        )
        if isinstance(seed_out, SeedMaterializeSkip):
            skip_whys.append(seed_out.why)
            continue
        stamped.extend(seed_out.wrote)
        max_L = max(max_L, len(seed_out.wrote))
        if seed_out.canal is not None:
            stamped_canals.append(seed_out.canal)

    stamped_cells = tuple(sorted(set(stamped)))
    return SegmentMaterializeResult(
        stamped=stamped_cells,
        width_used=max_L,
        canal=aggregate_canals(stamped_canals),
        extra_structure_refs=extras,
        skip_why=None if stamped_cells else _aggregate_skip_why(skip_whys),
    )


def materialize_seed(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    result: RoadShoulderGradeResult,
    *,
    seed: tuple[int, int],
    requested: int,
    h: int,
    kind: ReliefSideKind,
    sign: int,
    extras: tuple[str, ...],
    road_cells: set[tuple[int, int]],
    tile_set: set[tuple[int, int]],
    canal_registry: WorldCanalTemplateRegistry,
    canal_rules: Sequence[CanalObstaclePolicyRule],
) -> SeedStampResult | SeedMaterializeSkip:
    """One seed: clearance → canal → anchor → volume → stamp → Grade."""
    d = result.decision
    clearance = resolve_seed_clearance(
        seed=seed,
        road_cells=road_cells,
        requested_length=requested,
        world=ctx.world,
        cell_blocked=lambda c: cell_blocked_light(
            compose, c, tile_set=tile_set,
        ),
    )
    if isinstance(clearance, SeedClearanceSkip):
        relief_warning(
            EVENT_RIBBON_SKIP,
            site_id=result.segment.site_id,
            why=clearance.why,
            seed=clearance.seed,
            free_gap=clearance.free_gap,
            requested=clearance.requested,
            L_eff=clearance.L_eff,
        )
        return SeedMaterializeSkip(why=clearance.why)

    canal = resolve_seed_canal(
        requested_length=requested,
        L_eff=clearance.L_eff,
        terrain_key=result.segment.terrain_key,
        knobs_earthen=d.earthen_canal,
        knobs_structure_canal=d.structure_canal,
        policy_rules=canal_rules,
        registry=canal_registry,
        site_id=result.segment.site_id,
    )

    anchor = resolve_edge_road_anchor(
        compose, clearance, road_cells=road_cells, tile_set=tile_set,
    )
    if anchor is None:
        relief_warning(
            EVENT_RIBBON_SKIP,
            site_id=result.segment.site_id,
            why=WHY_NO_EDGE_ROAD_ANCHOR,
            seed=seed,
        )
        return SeedMaterializeSkip(why=WHY_NO_EDGE_ROAD_ANCHOR)

    plan = plan_seed_volume(
        decision_geom=result.decision.geom,
        h=h,
        kind=kind,
        L_eff=clearance.L_eff,
        z_road=anchor.z,
        sign=sign,
    )
    if plan is None or not plan.columns:
        relief_warning(
            EVENT_RIBBON_SKIP,
            site_id=result.segment.site_id,
            why=WHY_EMPTY_PLAN,
            seed=seed,
            L_eff=clearance.L_eff,
            h=h,
        )
        return SeedMaterializeSkip(why=WHY_EMPTY_PLAN)

    outcome = stamp_ribbon_plan(
        compose,
        seed=seed,
        plan=plan,
        kind=kind,
        sign=sign,
        anchor=anchor,
        road_cells=road_cells,
        tile_set=tile_set,
    )
    if outcome.break_why is not None:
        relief_debug(
            EVENT_RIBBON_SKIP,
            site_id=result.segment.site_id,
            why=outcome.break_why,
            seed=seed,
            cell=outcome.break_cell,
            wrote=len(outcome.wrote),
        )
    if not outcome.wrote:
        return SeedMaterializeSkip(why=outcome.break_why or WHY_EMPTY_STAMP)

    wrote = outcome.wrote
    facing = first_column_facing(compose, wrote[0], tile_set=tile_set)
    drawn = project_canal_draw(canal, extra_structure_refs=extras)
    grade = build_ribbon_grade_instance(
        world_uid=ctx.world.world_uid,
        site_id=result.segment.site_id,
        seed=seed,
        plan=plan,
        cell_refs=tuple(wrote),
        facing=facing,
        earthen_canal=drawn.earthen_canal,
        structure_refs=drawn.structure_refs,
        structure_canal=drawn.structure_canal,
        template_uid=result.template_uid,
        edge_uid=result.segment.edge_uid,
    )
    stamp_grade_uid(compose, wrote, grade.grade_uid, tile_set=tile_set)
    ctx.relief_grade_instances.append(grade)
    return SeedStampResult(wrote=wrote, canal=canal)
