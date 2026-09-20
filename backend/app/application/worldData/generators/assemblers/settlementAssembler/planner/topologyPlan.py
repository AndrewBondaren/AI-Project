"""Single writer for C23 slot + city-graph order — CITY-T-5i.

Assembler must not import ``SettlementGeneratorService`` (cycle). Call this
function from the generator wrapper and from assembler fallback.
"""

from __future__ import annotations

import random

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
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def plan_city_graph_for_slots(
    world: World,
    settlement: NamedLocation,
    skeleton: CitySkeleton,
    slots: list[DistrictSlot],
    terrain_cells: list[MapCell] | None,
) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
    origin = settlement_origin_fine(settlement)
    rng = random.Random(f"{world.world_uid}_{settlement.location_uid}")
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
) -> tuple[list[DistrictSlot], list[ConnectionNode], list[ConnectionEdge]]:
    slots = plan_district_slots(world, settlement, skeleton, terrain_cells)
    nodes, edges = plan_city_graph_for_slots(
        world, settlement, skeleton, slots, terrain_cells,
    )
    return slots, nodes, edges
