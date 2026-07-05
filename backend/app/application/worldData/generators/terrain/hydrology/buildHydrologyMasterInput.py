"""Assemble HydrologyMasterInput from world + DB graph — D HY-1d."""

from __future__ import annotations

from app.application.worldData.generators.terrain.hydrology.hydrologyLocations import (
    geographic_locations,
)
from app.application.worldData.generators.terrain.hydrology.loadConnectionGraph import (
    load_connection_graph,
)
from app.application.worldData.generators.terrain.hydrology.declaredEdges import (
    extract_declared_segments,
)
from app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.hydrology.lakeSpecs import extract_lake_specs
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.application.worldData.generators.terrain.hydrology.types import (
    HYDROLOGY_BOOTSTRAP_SCOPES,
    HydrologyMasterInput,
    HydrologyScope,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def build_hydrology_master_input(
    world: World,
    locations: list[NamedLocation],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
    *,
    scopes: frozenset[HydrologyScope] | None = None,
) -> HydrologyMasterInput:
    graph = load_connection_graph(world, locations, nodes, edges)
    active_scopes = scopes if scopes is not None else HYDROLOGY_BOOTSTRAP_SCOPES
    coastline_segments = extract_declared_segments(
        graph,
        HydrologyConnectionType.COASTLINE,
    )
    lake_specs = extract_lake_specs(graph, locations, world_uid=world.world_uid)
    return HydrologyMasterInput(
        world_uid=world.world_uid,
        hydrology_enabled=is_hydrology_enabled(world),
        scopes=active_scopes,
        connection_graph=graph,
        geographic_locations=geographic_locations(locations),
        declared_coastline_segments=coastline_segments,
        declared_lake_specs=lake_specs,
    )
