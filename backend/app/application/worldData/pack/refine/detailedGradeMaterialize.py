"""Materialize relief grade uid on meter grid — R36u / R36t corridor only."""

from __future__ import annotations

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.relief.edgeRoadAnchor import (
    EdgeRoadAnchor,
    edge_road_abutment,
)
from app.application.worldData.generators.terrain.relief.facing import (
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.gradeInstanceFactory import (
    build_ribbon_grade_instance,
)
from app.application.worldData.generators.terrain.relief.ribbonGrade import RibbonGradeResult
from app.application.worldData.generators.terrain.relief.ribbonSeedResolve import (
    SeedClearance,
    SeedClearanceSkip,
    resolve_seed_clearance,
)
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    plan_seed_volume,
    ribbon_sign_from_dz,
)
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
    meter_grade_cell_blocked,
)
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.world import World


def r36t_corridor_cells(
    wrote: tuple[Coord, ...],
    ref_cells: set[Coord],
) -> tuple[Coord, ...]:
    """Stamp uid on grade columns; never on high anchors (ref). Low = one step past last wrote."""
    return tuple(c for c in wrote if c not in ref_cells)


def resolve_meter_anchor(
    surface: MeterGradeSurface,
    clearance: SeedClearance,
    *,
    ref_cells: set[Coord],
) -> EdgeRoadAnchor | None:
    abutment = edge_road_abutment(
        clearance.seed, clearance.outward, ref_cells,
    )
    if abutment is None:
        return None
    z = surface.z_at(abutment)
    if z is None:
        return None
    ax, ay = abutment
    return EdgeRoadAnchor(
        xy=abutment,
        outward=clearance.outward,
        z=int(z),
        center_m=(ax + 0.5, ay + 0.5),
    )


def _meter_outward_columns(
    seed: Coord,
    outward: tuple[int, int],
    *,
    length: int,
) -> tuple[Coord, ...]:
    dx, dy = outward
    sx, sy = seed
    return tuple((sx + dx * k, sy + dy * k) for k in range(length))


def stamp_instance_uids(
    surface: MeterGradeSurface,
    instance: ReliefGradeInstance,
) -> None:
    for xy in instance.cell_refs:
        surface.stamp_grade(xy, instance.grade_uid)


def materialize_segment_meter(
    surface: MeterGradeSurface,
    world: World,
    result: RibbonGradeResult,
    *,
    ref_cells: set[Coord],
) -> list[ReliefGradeInstance]:
    """One Grade instance per seed; uid on R36t corridor only."""
    kind = result.decision.kind
    if kind is None or result.decision.skipped:
        return []
    h = int(result.decision.h)
    requested = max(0, int(result.decision.requested_length))
    if h < 1:
        return []

    sign = ribbon_sign_from_dz(int(result.segment.dz))
    road_key = terrain_masks(world).default_roads.system_terrain
    barrier_keys = WorldTerrainRegistry.canonical_barrier_terrain_keys()
    instances: list[ReliefGradeInstance] = []

    for seed in result.segment.cell_coords:
        clearance = resolve_seed_clearance(
            seed=seed,
            ref_cells=ref_cells,
            requested_length=requested,
            world=world,
            cell_blocked=lambda c: meter_grade_cell_blocked(
                surface, c, road_key=road_key, barrier_keys=barrier_keys,
            ),
        )
        if isinstance(clearance, SeedClearanceSkip):
            continue

        anchor = resolve_meter_anchor(surface, clearance, ref_cells=ref_cells)
        if anchor is None:
            continue

        plan = plan_seed_volume(
            decision_geom=result.decision.geom,
            h=h,
            kind=kind,
            L_eff=clearance.L_eff,
            z_road=anchor.z,
            sign=sign,
        )
        if plan is None or not plan.columns:
            continue

        wrote = _meter_outward_columns(
            seed, anchor.outward, length=len(plan.columns),
        )
        corridor = r36t_corridor_cells(wrote, ref_cells)
        if not corridor:
            continue

        facing = facing_wire(
            uphill_facing_toward(
                float(corridor[0][0]), float(corridor[0][1]),
                float(anchor.xy[0]), float(anchor.xy[1]),
            ),
        )
        inst = build_ribbon_grade_instance(
            world_uid=world.world_uid,
            site_id=result.segment.site_id,
            seed=seed,
            plan=plan,
            cell_refs=corridor,
            facing=facing,
            template_uid=result.template_uid,
            owner_uid=result.segment.owner_uid,
        )
        stamp_instance_uids(surface, inst)
        instances.append(inst)

    return instances
