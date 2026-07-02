"""Bin-packing area slots по реальному bbox из layout cache."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    lookup_building_template,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    building_tier_compatible,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)
from app.dataModel.spatial.facing import Facing
from app.db.models.world import World

logger = logging.getLogger(__name__)

PARCEL_GAP_M = 8


@dataclass(frozen=True)
class AreaPlacement:
    area_slot:   AreaSlot
    template:    dict
    building_x:  int  # WORLD_LOCAL_METERS
    building_y:  int  # WORLD_LOCAL_METERS


def _district_bounds(slot: DistrictSlot) -> tuple[int, int, int, int]:
    return (
        slot.origin_x,
        slot.origin_y,
        slot.origin_x + slot.width_m,
        slot.origin_y + slot.depth_m,
    )


def _footprint_rect(fp: OccupiedFootprint, building_x: int, building_y: int) -> tuple[int, int, int, int]:
    x0 = building_x + fp.min_x
    y0 = building_y + fp.min_y
    x1 = x0 + fp.width - 1
    y1 = y0 + fp.depth - 1
    return x0, y0, x1, y1


def _rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1


def _fits_district(
    slot: DistrictSlot,
    fp:   OccupiedFootprint,
    bx:   int,
    by:   int,
) -> tuple[bool, str]:
    ox0, oy0, ox1, oy1 = _district_bounds(slot)
    x0, y0, x1, y1 = _footprint_rect(fp, bx, by)
    if x0 < ox0 or y0 < oy0 or x1 >= ox1 or y1 >= oy1:
        return False, "выход за границы района"
    return True, ""


def _position_center(slot: DistrictSlot, fp: OccupiedFootprint) -> tuple[int, int]:
    cx = slot.origin_x + slot.width_m // 2
    cy = slot.origin_y + slot.depth_m // 2
    bx = cx - fp.width // 2 - fp.min_x
    by = cy - fp.depth // 2 - fp.min_y
    return bx, by


def _position_any(slot: DistrictSlot, fp: OccupiedFootprint, margin: int = PARCEL_GAP_M) -> tuple[int, int]:
    return slot.origin_x + margin - fp.min_x, slot.origin_y + margin - fp.min_y


def _make_area_slot(
    fp:       OccupiedFootprint,
    bx:       int,
    by:       int,
    ground_z: int,
    facing:   Facing,
) -> AreaSlot:
    x0, y0, x1, y1 = _footprint_rect(fp, bx, by)
    cells = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    return AreaSlot(cells=cells, ground_z=ground_z, facing=facing)


def plan_area_placements(
    slot:         DistrictSlot,
    layout_cache: dict[str, StructureLayout],
    world:        World,
    skeleton:     CitySkeleton,
    rng:          random.Random,
) -> list[AreaPlacement]:
    """
    generate-first, place-second: bbox из cache, required_structures первыми.
    """
    district_name = slot.district_template.system_name
    placed_rects: list[tuple[int, int, int, int]] = []
    placements: list[AreaPlacement] = []

    def try_place(
        template_name: str,
        position:      str,
        facing:        Facing = Facing.SOUTH,
    ) -> bool:
        template = lookup_building_template(world, template_name)
        if template is None:
            logger.warning(
                "district=%s template=%s не размещён: шаблон не найден",
                district_name,
                template_name,
            )
            return False

        if not building_tier_compatible(template, skeleton, world):
            logger.warning(
                "district=%s template=%s не размещён: economic_tier несовместим",
                district_name,
                template_name,
            )
            return False

        cached = layout_cache.get(template_name)
        if cached is None or cached.occupied_footprint is None:
            logger.warning(
                "district=%s template=%s не размещён: нет layout в cache",
                district_name,
                template_name,
            )
            return False

        fp = cached.occupied_footprint
        if position == "center":
            bx, by = _position_center(slot, fp)
        else:
            bx, by = _position_any(slot, fp)

        ok, reason = _fits_district(slot, fp, bx, by)
        if not ok:
            logger.warning(
                "district=%s template=%s не размещён: %s (bbox=%dx%d, свободно=%dx%d)",
                district_name,
                template_name,
                reason,
                fp.width,
                fp.depth,
                slot.width_m,
                slot.depth_m,
            )
            return False

        rect = _footprint_rect(fp, bx, by)
        for other in placed_rects:
            if _rects_overlap(rect, other):
                logger.warning(
                    "district=%s template=%s не размещён: пересечение с уже размещённым зданием",
                    district_name,
                    template_name,
                )
                return False

        area_slot = _make_area_slot(fp, bx, by, slot.ground_z, facing)
        placements.append(AreaPlacement(
            area_slot=area_slot,
            template=template,
            building_x=bx,
            building_y=by,
        ))
        placed_rects.append(rect)
        return True

    for req in slot.required_structures:
        name = req.building_template
        if not name:
            continue
        count = int(req.count or 1)
        position = req.position or "any"
        for _ in range(count):
            try_place(name, position)

    allowed = slot.district_template.allowed_structure_types
    if allowed:
        candidates = [
            n for n, layout in layout_cache.items()
            if layout.occupied_footprint is not None
            and lookup_building_template(world, n) is not None
            and building_tier_compatible(lookup_building_template(world, n), skeleton, world)
            and (
                (lookup_building_template(world, n).get("structure_type")
                 or lookup_building_template(world, n).get("system_type")) in allowed
            )
        ]
        rng.shuffle(candidates)
        step = max(
            (layout_cache[n].occupied_footprint.width for n in candidates),
            default=20,
        ) + PARCEL_GAP_M
        margin = PARCEL_GAP_M
        for name in candidates:
            if any(p.template.get("system_name") == name for p in placements):
                continue
            fp = layout_cache[name].occupied_footprint
            placed = False
            y = slot.origin_y + margin
            while y + fp.depth < slot.origin_y + slot.depth_m - margin and not placed:
                x = slot.origin_x + margin
                while x + fp.width < slot.origin_x + slot.width_m - margin and not placed:
                    bx = x - fp.min_x
                    by = y - fp.min_y
                    ok, reason = _fits_district(slot, fp, bx, by)
                    rect = _footprint_rect(fp, bx, by)
                    if ok and not any(_rects_overlap(rect, r) for r in placed_rects):
                        area_slot = _make_area_slot(fp, bx, by, slot.ground_z, Facing.SOUTH)
                        placements.append(AreaPlacement(
                            area_slot=area_slot,
                            template=lookup_building_template(world, name),
                            building_x=bx,
                            building_y=by,
                        ))
                        placed_rects.append(rect)
                        placed = True
                    x += step
                y += step
            if not placed:
                logger.warning(
                    "district=%s template=%s не размещён: недостаточно места (bbox=%dx%d, свободно=%dx%d)",
                    district_name,
                    name,
                    fp.width,
                    fp.depth,
                    slot.width_m,
                    slot.depth_m,
                )

    logger.info(
        "plan_area_placements | district=%s placements=%d required=%d",
        district_name,
        len(placements),
        len(slot.required_structures),
    )
    return placements
