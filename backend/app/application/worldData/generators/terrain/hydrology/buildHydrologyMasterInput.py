"""Assemble HydrologyMasterInput from world POJO declare — hard cut from connection graph."""

from __future__ import annotations

from app.application.worldData.generators.terrain.hydrology.hydrologyLocations import (
    geographic_locations,
)
from app.application.worldData.generators.terrain.hydrology.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    HYDROLOGY_BOOTSTRAP_SCOPES,
    HydrologyMasterInput,
    HydrologyScope,
    LoadedConnectionGraph,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def build_hydrology_master_input(
    world: World,
    locations: list[NamedLocation],
    nodes: list[ConnectionNode] | None = None,
    edges: list[ConnectionEdge] | None = None,
    *,
    scopes: frozenset[HydrologyScope] | None = None,
) -> HydrologyMasterInput:
    _ = nodes, edges  # roads / future; hydrology declare no longer from graph
    declared = load_declared_hydrology(world, locations)
    active_scopes = scopes if scopes is not None else HYDROLOGY_BOOTSTRAP_SCOPES
    return HydrologyMasterInput(
        world_uid=world.world_uid,
        hydrology_enabled=is_hydrology_enabled(world),
        scopes=active_scopes,
        connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        geographic_locations=geographic_locations(locations),
        declared_coastline_segments=declared.coastline_segments,
        declared_lake_specs=declared.lake_specs,
        declared_river_edges=declared.river_edges,
        declared_river_intents=declared.river_intents,
    )
