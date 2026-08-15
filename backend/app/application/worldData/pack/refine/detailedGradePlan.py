"""Planned grade occupancy types — shared by generate and face-graph stitch.

Breaks the generate ↔ graph import cycle. SoT: ``tz_terrain_relief.md`` C28.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.worldData.generators.terrain.relief.pick.ribbonGrade import RibbonGradeResult
from app.application.worldData.generators.terrain.relief.geom.outward import unique_outward
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.dataModel.spatial.facing import Facing, cardinal_facing_for_delta
from app.dataModel.terrain.relief.enums import ReliefContext, ReliefSideKind


@dataclass(frozen=True, slots=True)
class GradeStraightKey:
    """One C28 straight: ``(kind, outward, θ)``. Outward is volume corridor Facing."""

    kind: ReliefSideKind
    outward: Facing | None
    angle_deg: float | None


@dataclass(frozen=True, slots=True)
class PlannedGradeSegment:
    context: ReliefContext
    result: RibbonGradeResult
    ref_cells: frozenset[Coord]
    grade_uid: str


def outward_facing_for_seed(seed: Coord, ref_cells: set[Coord]) -> Facing | None:
    if not ref_cells:
        return None
    return cardinal_facing_for_delta(unique_outward(seed, ref_cells))


def straight_key(item: PlannedGradeSegment) -> GradeStraightKey | None:
    """``(kind, outward, θ)`` or None when the segment is not a grade straight."""
    decision = item.result.decision
    if decision.skipped or decision.kind is None:
        return None
    seeds = item.result.segment.cell_coords
    if not seeds:
        return None
    refs = set(item.ref_cells)
    facings = {outward_facing_for_seed(seed, refs) for seed in seeds}
    outward = next(iter(facings)) if len(facings) == 1 else None
    angle = None if decision.geom is None else decision.geom.angle_deg
    return GradeStraightKey(kind=decision.kind, outward=outward, angle_deg=angle)


def split_mixed_outward(item: PlannedGradeSegment) -> list[PlannedGradeSegment]:
    """One segment with two corridor outwards → two occupancy rows (T-3b)."""
    seeds = item.result.segment.cell_coords
    if len(seeds) < 2:
        return [item]
    refs = set(item.ref_cells)
    buckets: dict[Facing | None, list[Coord]] = {}
    order: list[Facing | None] = []
    for seed in seeds:
        facing = outward_facing_for_seed(seed, refs)
        if facing not in buckets:
            order.append(facing)
            buckets[facing] = []
        buckets[facing].append(seed)
    if len(buckets) <= 1:
        return [item]
    parts: list[PlannedGradeSegment] = []
    for facing in order:
        cells = tuple(buckets[facing])
        segment = replace(item.result.segment, cell_coords=cells)
        result = replace(item.result, segment=segment)
        parts.append(replace(item, result=result, grade_uid=""))
    return parts
