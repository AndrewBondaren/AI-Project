"""road_shoulder grade sites — segmentize + classify (R20–R28 data out).

Pure consumer: emits RibbonGradeDecision with raw canal knobs.
Registry/policy resolve happens once in bake (RELIEF-T-51).
Barrier stamp = bake ``roadShoulderBarrierApply`` (RELIEF-BAR-1); not this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.jsonValidation.worldRow import (
    relief_pick_policy,
    relief_template_registry,
)
from app.application.worldData.generators.terrain.relief.gradePass import (
    RibbonGradeDecision,
    grade_from_template,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_ROAD_SHOULDER_SKIP,
    WHY_NO_TEMPLATE_BODY,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_info
from app.application.worldData.generators.terrain.relief.templatePick import pick_template
from app.application.worldData.generators.terrain.relief.terrainMap import map_system_terrain
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy
from app.db.models.world import World


@dataclass(frozen=True, slots=True)
class RoadShoulderSegment:
    """One pick site: contiguous corridor terrain × side along an edge."""

    edge_uid: str
    terrain_key: str  # ReliefConditionTerrain value
    system_terrain: str
    dz: int
    site_id: str
    cell_coords: tuple[tuple[int, int], ...]  # (x,y) shoulder cells


@dataclass(frozen=True, slots=True)
class RoadShoulderGradeResult:
    segment: RoadShoulderSegment
    decision: RibbonGradeDecision
    template_uid: str | None


def segmentize_by_terrain(
    *,
    edge_uid: str,
    cells: list[tuple[tuple[int, int], str, int]],
) -> list[RoadShoulderSegment]:
    """Split shoulder cells into segments on system_terrain change.

    cells: ((x,y), system_terrain, dz) in stable walk order along the edge side.
    """
    segments: list[RoadShoulderSegment] = []
    if not cells:
        return segments

    buf_coords: list[tuple[int, int]] = []
    cur_terrain = cells[0][1]
    cur_dz = cells[0][2]
    for (xy, terrain, dz) in cells:
        mapped = map_system_terrain(terrain)
        if mapped is None:
            # flush and skip
            if buf_coords:
                key = map_system_terrain(cur_terrain)
                if key is not None:
                    segments.append(_seg(edge_uid, key.value, cur_terrain, cur_dz, buf_coords))
                buf_coords = []
            cur_terrain = terrain
            cur_dz = dz
            continue
        if terrain != cur_terrain:
            key = map_system_terrain(cur_terrain)
            if key is not None and buf_coords:
                segments.append(_seg(edge_uid, key.value, cur_terrain, cur_dz, buf_coords))
            buf_coords = [xy]
            cur_terrain = terrain
            cur_dz = dz
        else:
            buf_coords.append(xy)
            cur_dz = dz
    if buf_coords:
        key = map_system_terrain(cur_terrain)
        if key is not None:
            segments.append(_seg(edge_uid, key.value, cur_terrain, cur_dz, buf_coords))
    return segments


def _seg(
    edge_uid: str,
    terrain_key: str,
    system_terrain: str,
    dz: int,
    coords: list[tuple[int, int]],
) -> RoadShoulderSegment:
    site_id = f"{edge_uid}|{terrain_key}|{coords[0][0]},{coords[0][1]}"
    return RoadShoulderSegment(
        edge_uid=edge_uid,
        terrain_key=terrain_key,
        system_terrain=system_terrain,
        dz=dz,
        site_id=site_id,
        cell_coords=tuple(coords),
    )


def grade_road_shoulder_segments(
    *,
    world: World,
    world_seed: str,
    segments: list[RoadShoulderSegment],
    templates_by_uid: dict[str, ReliefTemplate],
    object_policy: ObjectReliefPickPolicy | None = None,
    occurrence_start: int = 0,
) -> list[RoadShoulderGradeResult]:
    registry = relief_template_registry(world)
    world_policy = relief_pick_policy(world)
    results: list[RoadShoulderGradeResult] = []
    seq = occurrence_start
    for segment in segments:
        pick = pick_template(
            context=ReliefContext.ROAD_SHOULDER,
            registry=registry,
            world_policy=world_policy,
            world_seed=world_seed,
            site_id=segment.site_id,
            occurrence_seq=seq,
            object_policy=object_policy,
        )
        seq += 1
        if not pick.template_uid or pick.template_uid not in templates_by_uid:
            relief_info(
                EVENT_ROAD_SHOULDER_SKIP,
                site_id=segment.site_id,
                reason=WHY_NO_TEMPLATE_BODY,
                template_uid=pick.template_uid,
            )
            continue
        template = templates_by_uid[pick.template_uid]
        decision = grade_from_template(
            template=template,
            template_uid=pick.template_uid,
            terrain_key=segment.terrain_key,
            dz=segment.dz,
            world_seed=world_seed,
            site_id=segment.site_id,
        )
        results.append(
            RoadShoulderGradeResult(
                segment=segment,
                decision=decision,
                template_uid=pick.template_uid,
            )
        )
        relief_info(
            "road_shoulder_apply",
            site_id=segment.site_id,
            template_uid=pick.template_uid,
            policy_level=pick.policy_level,
            skipped=decision.skipped,
            kind=None if decision.kind is None else decision.kind.value,
            earthen_canal=decision.earthen_canal,
            structure_canal=decision.structure_canal,
            structure_refs=list(decision.structure_refs),
            width=decision.requested_length,
        )
    return results
