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
    expand_bbox,
    gate_on_facing_edge,
    perimeter_ring_bbox,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

_PARCEL_MARGIN_M = 1


def _perimeter_barrier_spec(building_template: dict) -> dict:
    return building_template.get("perimeter_barrier") or {}


def should_build_area_barrier(
    building_template: dict,
    rng:               Random,
) -> bool:
    spec = _perimeter_barrier_spec(building_template)
    template_type = spec.get("template")
    if not template_type:
        return False
    probability = float(spec.get("probability", 0.0))
    if probability <= 0.0:
        return False
    if probability >= 1.0:
        return True
    return rng.random() < probability


def plan_area_barrier_cells(
    world:             World,
    slot:              AreaSlot,
    building_template: dict,
    building:          NamedLocation,
    skeleton:          CitySkeleton,
    rng:               Random,
) -> list[MapCell]:
    """
    Забор вокруг footprint участка (slot.cells) + margin.
    CoordinateSpace: WORLD_LOCAL_METERS (parcel bbox from slot.cells).
    Gate — на грани slot.facing (сторона улицы).
    """
    if not slot.cells:
        return []

    if not should_build_area_barrier(building_template, rng):
        return []

    spec = _perimeter_barrier_spec(building_template)
    template_type = spec.get("template")
    barrier_template = lookup_barrier_template(world, template_type) if template_type else None
    if barrier_template is None:
        logger.warning(
            "plan_area_barrier | building=%s template=%r not found in barrier_template_registry",
            building_template.get("system_name", "?"),
            template_type,
        )
        return []

    bx0, by0, bx1, by1 = bbox_from_cells(slot.cells)
    px0, py0, px1, py1 = expand_bbox(bx0, by0, bx1, by1, _PARCEL_MARGIN_M)
    ring = set(perimeter_ring_bbox(px0, py0, px1, py1, step=1))
    gate = gate_on_facing_edge(px0, py0, px1, py1, slot.facing)
    gate_coords = {gate}
    ring |= gate_coords

    material = pick_barrier_material(
        world, barrier_template, skeleton.economic_tier, rng,
    )
    cells = emit_barrier_cells(
        world, ring, gate_coords, material, building.location_uid, slot.ground_z,
    )

    logger.info(
        "plan_area_barrier | building=%s barrier_template=%s material=%s"
        " cells=%d parcel=(%d,%d)-(%d,%d) facing=%s",
        building_template.get("system_name", "?"),
        template_type,
        material,
        len(cells),
        px0,
        py0,
        px1,
        py1,
        slot.facing,
    )
    return cells
