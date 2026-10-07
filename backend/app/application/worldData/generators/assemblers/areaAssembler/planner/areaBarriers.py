"""Area parcel barriers — building template perimeter_barrier + barrier_template_registry."""

from __future__ import annotations

import logging
from random import Random

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
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
from app.dataModel.locations.settlement.area.perimeterBarrier import perimeter_barrier_from_template
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionParams import GateTransitionParams
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.spatial.facing import GRID_OUTWARD_DELTA
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

logger = logging.getLogger(__name__)


def area_gate_cells(barrier_cells: list[MapCell]) -> list[MapCell]:
    gate_key = WorldTerrainRegistry.require_engine_terrain_key("gate")
    return [cell for cell in barrier_cells if cell.system_terrain == gate_key]


def area_gate_transitions(world: World, slot: AreaSlot, barrier_cells: list[MapCell]) -> list[Transition]:
    """The actual opening joins adjacent surface cells; no area NL is required."""
    delta = GRID_OUTWARD_DELTA[slot.facing]
    result = []
    for gate in area_gate_cells(barrier_cells):
        source = TransitionEndpoint(x=gate.x + delta[0], y=gate.y + delta[1], z=gate.z)
        destination = TransitionEndpoint(x=gate.x - delta[0], y=gate.y - delta[1], z=gate.z)
        result.append(Transition(
            transition_uid=transition_uid(world.world_uid, TransitionType.GATE, source, destination),
            world_uid=world.world_uid, system_transition_type=TransitionType.GATE,
            source=source, destination=destination, type_params=GateTransitionParams(width_cells=1)))
    return result


def should_build_area_barrier(
    building_template: PlotLayoutTemplate,
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
    building_template: PlotLayoutTemplate,
    building:          NamedLocation | None,
    skeleton:          SettlementSkeleton,
    rng:               Random,
) -> list[MapCell]:
    """
    Забор по периметру уже готовых slot.cells. Не expand.
    Gate — на грани slot.facing (сторона улицы); фасад входа смотрит на main_building.
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
            building_template.system_name,
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
        building_template.system_name,
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
