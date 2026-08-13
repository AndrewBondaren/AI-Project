"""Materialize relief grade uid on meter grid — R36u / R36t corridor only."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.jsonValidation import terrain_masks
from app.application.worldData.generators.terrain.relief.edgeRoadAnchor import (
    EdgeRoadAnchor,
    edge_road_abutment,
)
from app.application.worldData.generators.terrain.relief.facing import (
    CARDINAL_ORTHO_DELTAS,
    facing_wire,
    uphill_facing_toward,
)
from app.dataModel.spatial.facing import Facing
from app.application.worldData.generators.terrain.relief.gradeInstanceFactory import (
    build_ribbon_grade_instance,
    make_grade_uid,
)
from app.application.worldData.generators.terrain.relief.ribbonGrade import RibbonGradeResult
from app.application.worldData.generators.terrain.relief.ribbonSeedResolve import (
    SeedClearance,
    SeedClearanceSkip,
    resolve_seed_clearance,
)
from app.application.worldData.generators.terrain.relief.volumeMaterialize import (
    RibbonVolumePlan,
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


@dataclass(frozen=True, slots=True)
class SeedCorridor:
    """One seed's stamped corridor. Entity geom uses the last successful seed."""

    seed: Coord
    corridor: tuple[Coord, ...]
    plan: RibbonVolumePlan
    facing: Facing | None


def r36t_corridor_cells(
    wrote: tuple[Coord, ...],
    ref_cells: set[Coord],
) -> tuple[Coord, ...]:
    """Stamp uid on grade columns; never on high anchors (ref). Low = one step past last wrote."""
    return tuple(c for c in wrote if c not in ref_cells)


def local_grade_anchors(
    seed: Coord,
    *,
    ref_cells: set[Coord],
    segment_seeds: set[Coord],
    surface: MeterGradeSurface,
) -> set[Coord]:
    """Crests adjacent to ``seed``, else uphill cascade neighbor (R36v stitch)."""
    sx, sy = seed
    crests: set[Coord] = set()
    cascade: set[Coord] = set()
    z_seed = surface.z_at(seed)
    for dx, dy in CARDINAL_ORTHO_DELTAS:
        nb = (sx + dx, sy + dy)
        if nb in ref_cells and nb not in segment_seeds:
            crests.add(nb)
            continue
        if nb not in segment_seeds and nb not in ref_cells:
            continue
        z_nb = surface.z_at(nb)
        if z_seed is not None and z_nb is not None and int(z_nb) > int(z_seed):
            cascade.add(nb)
    return crests or cascade


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


def inherit_segment_uid(
    surface: MeterGradeSurface,
    seeds: tuple[Coord, ...],
    *,
    existing: dict[Coord, str] | None = None,
) -> str | None:
    """Reuse uid already on the ribbon. Exactly one neighbor uid; else None."""
    bag = existing or {}
    found: set[str] = set()
    for seed in seeds:
        for xy in (seed, *( (seed[0] + dx, seed[1] + dy) for dx, dy in CARDINAL_ORTHO_DELTAS )):
            uid = bag.get(xy) or surface.grade_uid.get(xy)
            if uid:
                found.add(uid)
    if len(found) != 1:
        return None
    return next(iter(found))


def resolve_segment_uid(
    *,
    world_uid: str,
    site_id: str,
    seeds: tuple[Coord, ...],
    surface: MeterGradeSurface | None = None,
    existing_uids: dict[Coord, str] | None = None,
    grade_uid: str | None = None,
) -> str:
    """Explicit uid, else inherit, else mint — one SoT (R36v-T-6)."""
    if grade_uid:
        return grade_uid
    grid = surface or MeterGradeSurface(
        surface_z={},
        surface_terrain={},
        hydrology=None,
        surface_facing=None,
    )
    inherited = inherit_segment_uid(grid, seeds, existing=existing_uids)
    if inherited:
        return inherited
    return make_grade_uid(world_uid=world_uid, site_id=site_id, seed=min(seeds))


def corridor_for_seed(
    surface: MeterGradeSurface,
    world: World,
    result: RibbonGradeResult,
    seed: Coord,
    *,
    ref_cells: set[Coord],
    segment_seeds: set[Coord],
    crest_refs: set[Coord],
    requested: int,
    h: int,
    sign: int,
    road_key: str,
    barrier_keys: frozenset[str],
) -> SeedCorridor | None:
    kind = result.decision.kind
    if kind is None:
        return None
    anchors = local_grade_anchors(
        seed,
        ref_cells=ref_cells,
        segment_seeds=segment_seeds,
        surface=surface,
    )
    if not anchors:
        return None
    clearance = resolve_seed_clearance(
        seed=seed,
        ref_cells=anchors,
        requested_length=requested,
        world=world,
        cell_blocked=lambda c: meter_grade_cell_blocked(
            surface, c, road_key=road_key, barrier_keys=barrier_keys,
        ),
    )
    if isinstance(clearance, SeedClearanceSkip):
        return None

    anchor = resolve_meter_anchor(surface, clearance, ref_cells=anchors)
    if anchor is None:
        return None

    plan = plan_seed_volume(
        decision_geom=result.decision.geom,
        h=h,
        kind=kind,
        L_eff=clearance.L_eff,
        z_road=anchor.z,
        sign=sign,
    )
    if plan is None or not plan.columns:
        return None

    wrote = _meter_outward_columns(
        seed, anchor.outward, length=len(plan.columns),
    )
    corridor = r36t_corridor_cells(wrote, crest_refs)
    if not corridor:
        return None

    facing = uphill_facing_toward(
        float(corridor[0][0]), float(corridor[0][1]),
        float(anchor.xy[0]), float(anchor.xy[1]),
    )
    return SeedCorridor(seed=seed, corridor=corridor, plan=plan, facing=facing)


def commit_segment(
    surface: MeterGradeSurface,
    result: RibbonGradeResult,
    *,
    world_uid: str,
    plan: RibbonVolumePlan,
    cell_refs: tuple[Coord, ...],
    facing: Facing | None,
    seeds: tuple[Coord, ...],
    grade_uid: str,
) -> ReliefGradeInstance:
    inst = build_ribbon_grade_instance(
        world_uid=world_uid,
        site_id=result.segment.site_id,
        seed=min(seeds),
        plan=plan,
        cell_refs=cell_refs,
        facing=facing_wire(facing),
        template_uid=result.template_uid,
        owner_uid=result.segment.owner_uid,
        grade_uid=grade_uid,
    )
    stamp_instance_uids(surface, inst)
    return inst


def materialize_segment_meter(
    surface: MeterGradeSurface,
    world: World,
    result: RibbonGradeResult,
    *,
    ref_cells: set[Coord],
    seeds: tuple[Coord, ...] | None = None,
    existing_uids: dict[Coord, str] | None = None,
    grade_uid: str | None = None,
) -> list[ReliefGradeInstance]:
    """One Grade instance per segment (R36v); uid on R36t corridor only."""
    kind = result.decision.kind
    if kind is None or result.decision.skipped:
        return []
    h = int(result.decision.h)
    requested = max(0, int(result.decision.requested_length))
    if h < 1:
        return []

    work_seeds = seeds if seeds is not None else result.segment.cell_coords
    if not work_seeds:
        return []

    segment_seeds = set(result.segment.cell_coords)
    crest_refs = {xy for xy in ref_cells if xy not in segment_seeds}
    sign = ribbon_sign_from_dz(int(result.segment.dz))
    road_key = terrain_masks(world).default_roads.system_terrain
    barrier_keys = WorldTerrainRegistry.canonical_barrier_terrain_keys()

    corridors: list[Coord] = []
    last: SeedCorridor | None = None
    for seed in work_seeds:
        piece = corridor_for_seed(
            surface, world, result, seed,
            ref_cells=ref_cells,
            segment_seeds=segment_seeds,
            crest_refs=crest_refs,
            requested=requested,
            h=h,
            sign=sign,
            road_key=road_key,
            barrier_keys=barrier_keys,
        )
        if piece is None:
            continue
        corridors.extend(piece.corridor)
        last = piece

    if last is None or not corridors:
        return []

    unique_refs = tuple(dict.fromkeys(corridors))
    uid = resolve_segment_uid(
        world_uid=world.world_uid,
        site_id=result.segment.site_id,
        seeds=work_seeds,
        surface=surface,
        existing_uids=existing_uids,
        grade_uid=grade_uid,
    )
    inst = commit_segment(
        surface, result,
        world_uid=world.world_uid,
        plan=last.plan,
        cell_refs=unique_refs,
        facing=last.facing,
        seeds=work_seeds,
        grade_uid=uid,
    )
    return [inst]
