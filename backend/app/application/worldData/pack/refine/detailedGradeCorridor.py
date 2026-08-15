"""Volume corridor for one seed — anchors, clearance, plan; no canal, no uid stamp."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.volume.edgeRoadAnchor import (
    EdgeRoadAnchor,
    cell_center_m,
    edge_road_abutment,
)
from app.application.worldData.generators.terrain.relief.geom.facing import CARDINAL_ORTHO_DELTAS
from app.application.worldData.generators.terrain.relief.volume.ribbonSeedResolve import (
    SeedClearance,
    SeedClearanceSkip,
    resolve_seed_clearance,
)
from app.application.worldData.generators.terrain.relief.geom.outward import unique_outward
from app.application.worldData.generators.terrain.relief.geom.geomResolve import ResolvedGeom
from app.application.worldData.generators.terrain.relief.volume.volumeMaterialize import (
    RibbonVolumePlan,
    plan_seed_volume,
)
from app.application.worldData.pack.refine.detailedGradeCatalog import TileFaceCatalog
from app.application.worldData.pack.refine.meterGradeSurface import (
    Coord,
    MeterGradeSurface,
    meter_grade_cell_blocked,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.db.models.world import World


@dataclass(frozen=True, slots=True)
class CorridorColumn:
    """One outward cell paired with its volume ``surface_z`` (plan ``k`` 1..L)."""

    xy: Coord
    surface_z: int
    k: int


@dataclass(frozen=True, slots=True)
class SeedCorridor:
    """Volume columns for one seed. Canal-cut and facing belong in apply."""

    seed: Coord
    columns: tuple[CorridorColumn, ...]
    plan: RibbonVolumePlan
    abutment: Coord
    requested: int
    L_eff: int

    @property
    def wrote(self) -> tuple[Coord, ...]:
        return tuple(col.xy for col in self.columns)

    def overlay_for(self, corridor: tuple[Coord, ...]) -> dict[Coord, int]:
        allowed = set(corridor)
        return {col.xy: col.surface_z for col in self.columns if col.xy in allowed}


def r36t_corridor_cells(
    wrote: tuple[Coord, ...],
    ref_cells: set[Coord],
    *,
    include_cut_end: bool = False,
) -> tuple[Coord, ...]:
    """Uid/z on grade columns; never on high anchors (ref).

    ``include_cut_end``: R36t canal-cut — last wrote cell may be a shortened-end
    ref when the named predicate is true.
    """
    corridor = tuple(c for c in wrote if c not in ref_cells)
    if include_cut_end and wrote:
        far = wrote[-1]
        if far not in corridor:
            corridor = (*corridor, far)
    return corridor


def outward_columns(
    seed: Coord,
    outward: tuple[int, int],
    *,
    length: int,
) -> tuple[Coord, ...]:
    """Ordered cells along ``outward``, seed first, ``length`` steps (k = 1..L)."""
    dx, dy = outward
    sx, sy = seed
    return tuple((sx + dx * k, sy + dy * k) for k in range(length))


def columns_for_plan(
    wrote: tuple[Coord, ...],
    plan: RibbonVolumePlan,
) -> tuple[CorridorColumn, ...]:
    """Pair each wrote cell with the plan column of the same outward index."""
    return tuple(
        CorridorColumn(xy=xy, surface_z=col.surface_z, k=col.k)
        for xy, col in zip(wrote, plan.columns, strict=True)
    )


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
    return EdgeRoadAnchor(
        xy=abutment,
        outward=clearance.outward,
        z=int(z),
        center_m=cell_center_m(abutment),
    )


def volume_corridor_for_seed(
    surface: MeterGradeSurface,
    world: World,
    seed: Coord,
    *,
    ref_cells: set[Coord],
    segment_seeds: set[Coord],
    requested: int,
    h: int,
    sign: int,
    kind: ReliefSideKind,
    decision_geom: ResolvedGeom | None,
    road_key: str,
    barrier_keys: frozenset[str],
    catalog: TileFaceCatalog | None = None,
) -> SeedCorridor | None:
    """Anchors → clearance → volume plan → paired columns. No canal, no R36t cut."""
    anchors = local_grade_anchors(
        seed,
        ref_cells=ref_cells,
        segment_seeds=segment_seeds,
        surface=surface,
    )
    if not anchors:
        return None
    outward = unique_outward(seed, anchors)
    flush_void = (
        catalog is not None
        and outward is not None
        and catalog.is_open_rim_step(seed, outward)
    )
    clearance = resolve_seed_clearance(
        seed=seed,
        ref_cells=anchors,
        requested_length=requested,
        world=world,
        cell_blocked=lambda c: meter_grade_cell_blocked(
            surface, c, road_key=road_key, barrier_keys=barrier_keys,
        ),
        flush_void=flush_void,
    )
    if isinstance(clearance, SeedClearanceSkip):
        return None

    anchor = resolve_meter_anchor(surface, clearance, ref_cells=anchors)
    if anchor is None:
        return None

    plan = plan_seed_volume(
        decision_geom=decision_geom,
        h=h,
        kind=kind,
        L_eff=clearance.L_eff,
        z_road=anchor.z,
        sign=sign,
    )
    if plan is None or not plan.columns:
        return None

    wrote = outward_columns(seed, anchor.outward, length=len(plan.columns))
    return SeedCorridor(
        seed=seed,
        columns=columns_for_plan(wrote, plan),
        plan=plan,
        abutment=anchor.xy,
        requested=requested,
        L_eff=clearance.L_eff,
    )
