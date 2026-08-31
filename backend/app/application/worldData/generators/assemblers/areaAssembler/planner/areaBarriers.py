"""Area parcel barriers — building template perimeter_barrier + barrier_template_registry."""

from __future__ import annotations

import logging
from random import Random

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.settlementAssembler.planner.barrierDefaults import (
    lookup_barrier_template,
)
from app.application.worldData.generators.barrier.cells import emit_barrier_cells
from app.application.worldData.generators.barrier.material import pick_barrier_material
from app.application.worldData.generators.barrier.perimeter import (
    bbox_from_cells,
    gate_on_facing_edge,
    perimeter_ring_bbox,
)
from app.dataModel.settlement.area.perimeterBarrier import perimeter_barrier_from_template
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def should_build_area_barrier(
    building_template: dict,
    rng:               Random,
) -> bool:
    spec = perimeter_barrier_from_template(building_template)
    if not spec.template:
        return False
    if spec.probability <= 0.0:
        return False
    if spec.probability >= 1.0:
        return True
    return rng.random() < spec.probability


def plan_area_barrier_cells(
    world:             World,
    slot:              AreaSlot,
    building_template: dict,
    building:          NamedLocation | None,
    skeleton:          CitySkeleton,
    rng:               Random,
) -> list[MapCell]:
    """
    Забор по периметру уже готовых slot.cells. Не expand.
    Gate — на грани slot.facing (сторона улицы).
    """
    if not slot.cells:
        return []

    if not should_build_area_barrier(building_template, rng):
        return []

    spec = perimeter_barrier_from_template(building_template)
    template_type = spec.template
    barrier_template = lookup_barrier_template(world, template_type) if template_type else None
    if barrier_template is None:
        logger.warning(
            "plan_area_barrier | building=%s template=%r not found in barrier_template_registry",
            building_template.get("system_name", "?"),
            template_type,
        )
        return []

    bx0, by0, bx1, by1 = bbox_from_cells(slot.cells)
    ring = set(perimeter_ring_bbox(bx0, by0, bx1, by1, step=1))
    gate = gate_on_facing_edge(bx0, by0, bx1, by1, slot.facing)
    gate_coords = {gate}
    ring |= gate_coords

    material = pick_barrier_material(
        world, barrier_template, skeleton.economic_tier, rng,
    )
    if building is not None:
        loc_uid = building.location_uid
    else:
        loc_uid = f"{world.world_uid}-area-{bx0}-{by0}"
    cells = emit_barrier_cells(
        world, ring, gate_coords, material, loc_uid, slot.ground_z,
    )

    logger.info(
        "plan_area_barrier | building=%s barrier_template=%s material=%s"
        " cells=%d parcel=(%d,%d)-(%d,%d) facing=%s",
        building_template.get("system_name", "?"),
        template_type,
        material,
        len(cells),
        bx0,
        by0,
        bx1,
        by1,
        slot.facing,
    )
    return cells
