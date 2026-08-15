"""Assemble GradeFormation write-set — canal-cut + instance + uid. No surface z write."""

from __future__ import annotations

from app.application.jsonValidation import canal_templates, relief_pick_policy, terrain_masks
from app.application.worldData.generators.terrain.relief.canal.attachments import (
    knobs_extra_structure_refs,
    project_canal_draw,
)
from app.application.worldData.generators.terrain.relief.geom.facing import (
    CARDINAL_ORTHO_DELTAS,
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    build_ribbon_grade_instance,
    make_grade_uid,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.generators.terrain.relief.pick.ribbonGrade import RibbonGradeResult
from app.application.worldData.generators.terrain.relief.canal.seedResolve import aggregate_canals
from app.application.worldData.generators.terrain.relief.volume.volumeMaterialize import ribbon_sign_from_dz
from app.application.worldData.pack.refine.detailedGradeCanalCut import (
    canal_for_seed,
    r36t_include_cut_end,
)
from app.application.worldData.pack.refine.detailedGradeCatalog import TileFaceCatalog
from app.application.worldData.pack.refine.detailedGradeCorridor import (
    SeedCorridor,
    r36t_corridor_cells,
    volume_corridor_for_seed,
)
from app.application.worldData.pack.refine.detailedGradeResult import (
    DetailedGradeResult,
    GradeFormation,
)
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.canal import Canal
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.world import World


def inherit_segment_uid(
    seeds: tuple[Coord, ...],
    uids: dict[Coord, str],
) -> str | None:
    """Reuse uid already on the ribbon. Exactly one neighbor uid; else None."""
    found: set[str] = set()
    for seed in seeds:
        for xy in (seed, *( (seed[0] + dx, seed[1] + dy) for dx, dy in CARDINAL_ORTHO_DELTAS )):
            uid = uids.get(xy)
            if uid:
                found.add(uid)
    if len(found) != 1:
        relief_debug(
            "grade_uid_inherit",
            hit=False,
            neighbor_count=len(found),
            neighbor_uids=tuple(sorted(found)) or None,
            seed_count=len(seeds),
            seed=min(seeds) if seeds else None,
        )
        return None
    uid = next(iter(found))
    relief_debug(
        "grade_uid_inherit",
        hit=True,
        grade_uid=uid,
        neighbor_count=1,
        seed_count=len(seeds),
        seed=min(seeds),
    )
    return uid


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
    bag: dict[Coord, str] = dict(surface.grade_uid) if surface is not None else {}
    if existing_uids:
        bag.update(existing_uids)
    inherited = inherit_segment_uid(seeds, bag)
    if inherited:
        return inherited
    return make_grade_uid(world_uid=world_uid, site_id=site_id, seed=min(seeds))


def _facing_for_corridor(
    corridor: tuple[Coord, ...],
    abutment: Coord,
) -> Facing | None:
    origin = corridor[0]
    return uphill_facing_toward(
        float(origin[0]), float(origin[1]),
        float(abutment[0]), float(abutment[1]),
    )


def instance_for_formation(
    result: RibbonGradeResult,
    formation: GradeFormation,
    *,
    world_uid: str,
    seeds: tuple[Coord, ...],
) -> ReliefGradeInstance:
    drawn = project_canal_draw(
        formation.canal,
        extra_structure_refs=knobs_extra_structure_refs(
            earthen_canal=result.decision.earthen_canal,
            structure_canal=result.decision.structure_canal,
            structure_refs=result.decision.structure_refs,
        ),
    )
    return build_ribbon_grade_instance(
        world_uid=world_uid,
        site_id=result.segment.site_id,
        seed=min(seeds),
        plan=formation.plan,
        cell_refs=formation.corridor,
        facing=facing_wire(formation.facing),
        earthen_canal=drawn.earthen_canal,
        structure_refs=drawn.structure_refs,
        structure_canal=drawn.structure_canal,
        template_uid=result.template_uid,
        owner_uid=result.segment.owner_uid,
        grade_uid=formation.grade_uid,
    )


def _cut_corridor(
    volume: SeedCorridor,
    canal: Canal | None,
    crest_refs: set[Coord],
) -> tuple[Coord, ...] | None:
    corridor = r36t_corridor_cells(
        volume.wrote,
        crest_refs,
        include_cut_end=r36t_include_cut_end(
            canal=canal, L_eff=volume.L_eff, requested=volume.requested,
        ),
    )
    return corridor or None


def materialize_segment_meter(
    surface: MeterGradeSurface,
    world: World,
    result: RibbonGradeResult,
    *,
    ref_cells: set[Coord],
    seeds: tuple[Coord, ...] | None = None,
    existing_uids: dict[Coord, str] | None = None,
    grade_uid: str | None = None,
    catalog: TileFaceCatalog | None = None,
) -> DetailedGradeResult:
    """One Grade per segment; returns the write-set (does not stamp the surface)."""
    kind = result.decision.kind
    if kind is None or result.decision.skipped:
        return DetailedGradeResult.empty()
    h = int(result.decision.h)
    requested = max(0, int(result.decision.requested_length))
    if h < 1:
        return DetailedGradeResult.empty()

    work_seeds = seeds if seeds is not None else result.segment.cell_coords
    if not work_seeds:
        return DetailedGradeResult.empty()

    segment_seeds = set(result.segment.cell_coords)
    crest_refs = {xy for xy in ref_cells if xy not in segment_seeds}
    sign = ribbon_sign_from_dz(int(result.segment.dz))
    road_key = terrain_masks(world).default_roads.system_terrain
    barrier_keys = WorldTerrainRegistry.canonical_barrier_terrain_keys()
    policy_rules = tuple(relief_pick_policy(world).canal_obstacle_policy)
    registry = canal_templates(world)

    overlay: dict[Coord, int] = {}
    corridors: list[Coord] = []
    canals: list[Canal] = []
    canonical: SeedCorridor | None = None
    facing: Facing | None = None
    for seed in work_seeds:
        volume = volume_corridor_for_seed(
            surface, world, seed,
            ref_cells=ref_cells,
            segment_seeds=segment_seeds,
            requested=requested,
            h=h,
            sign=sign,
            kind=kind,
            decision_geom=result.decision.geom,
            road_key=road_key,
            barrier_keys=barrier_keys,
            catalog=catalog,
        )
        if volume is None:
            continue
        canal = canal_for_seed(
            result,
            requested=volume.requested,
            L_eff=volume.L_eff,
            policy_rules=policy_rules,
            registry=registry,
        )
        corridor = _cut_corridor(volume, canal, crest_refs)
        if corridor is None:
            continue
        overlay.update(volume.overlay_for(corridor))
        corridors.extend(corridor)
        if canal is not None:
            canals.append(canal)
        if canonical is None or volume.plan.L > canonical.plan.L:
            canonical = volume
            facing = _facing_for_corridor(corridor, volume.abutment)

    if canonical is None or not corridors:
        return DetailedGradeResult.empty()

    unique_refs = tuple(dict.fromkeys(corridors))
    allowed = set(unique_refs)
    uid = resolve_segment_uid(
        world_uid=world.world_uid,
        site_id=result.segment.site_id,
        seeds=work_seeds,
        surface=surface,
        existing_uids=existing_uids,
        grade_uid=grade_uid,
    )
    formation = GradeFormation(
        plan=canonical.plan,
        overlay={xy: z for xy, z in overlay.items() if xy in allowed},
        corridor=unique_refs,
        facing=facing,
        canal=aggregate_canals(canals),
        grade_uid=uid,
    )
    inst = instance_for_formation(
        result, formation, world_uid=world.world_uid, seeds=work_seeds,
    )
    return formation.to_write_set(inst)
