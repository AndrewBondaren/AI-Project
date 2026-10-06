"""Single writer for C23 slot + city-graph order — CITY-T-5i.

Assembler must not import ``SettlementGeneratorService`` (cycle). Call this
function from the generator wrapper and from assembler fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionSide import TransitionSide
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
    plan_district_slots,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_side_fine,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import (
    plan_city_street_grid,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.terrain import (
    column_surface,
)
from app.application.worldData.generators.coordinates import (
    map_cell_fine_span,
    settlement_origin_fine,
)
from app.application.worldData.ids import UidKind, entity_rng
from app.dataModel.locations.context.locationContext import LocationContext
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class SettlementTopologyPlan:
    slots: list[DistrictSlot]
    nodes: list[ConnectionNode]
    edges: list[ConnectionEdge]
    transitions: list[Transition]


def settlement_gate_transitions(settlement: NamedLocation, nodes: list[ConnectionNode]) -> list[Transition]:
    """Existing city gates anchor arrival; outside surface stays symbolic."""
    result = []
    for node in nodes:
        if (node.node_type != ConnectionNodeType.SETTLEMENT_GATE.value
                or node.graph_level != GraphLevel.CITY.value):
            continue
        source = TransitionEndpoint()
        destination = TransitionEndpoint(host_location_uid=settlement.location_uid,
            node_uid=node.node_uid, x=node.x, y=node.y, z=node.z)
        system_type = TransitionType.MAIN_ENTRANCE
        result.append(Transition(
            transition_uid=transition_uid(settlement.world_uid, system_type, source, destination),
            world_uid=settlement.world_uid, system_transition_type=system_type,
            source=source, destination=destination,
            destination_side=TransitionSide(owner_location_uid=settlement.location_uid)))
    return result


def plan_city_graph_for_slots(
    world: World,
    settlement: NamedLocation,
    skeleton: CitySkeleton,
    slots: list[DistrictSlot],
    terrain_cells: list[MapCell] | None,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    origin = settlement_origin_fine(settlement)
    rng = entity_rng(
        world.world_uid, UidKind.TOPOLOGY, settlement=settlement.location_uid)
    return plan_city_street_grid(
        origin.x, origin.y, origin.z,
        footprint_side_fine(world, skeleton.system_city_size),
        map_cell_fine_span(world),
        slots, world.world_uid, world, rng, skeleton,
        surface=column_surface(terrain_cells),
        settlement_uid=settlement.location_uid,
    )


def plan_slots_and_city_graph(
    world: World,
    settlement: NamedLocation,
    skeleton: CitySkeleton,
    terrain_cells: list[MapCell] | None,
    settlement_ctx: LocationContext | None = None,
) -> SettlementTopologyPlan:
    slots = plan_district_slots(
        world, settlement, skeleton, terrain_cells, settlement_ctx,
    )
    nodes, edges = plan_city_graph_for_slots(
        world, settlement, skeleton, slots, terrain_cells,
    )
    return SettlementTopologyPlan(slots, nodes, edges, settlement_gate_transitions(settlement, nodes))
