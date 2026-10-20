"""Assemble HydrologyMasterInput from world POJO declare — hard cut from connection graph."""

from __future__ import annotations

from dataclasses import replace

from app.application.worldData.generators.coordinates.convert import (
    fine_segments_to_grid,
    map_cell_fine_span,
)
from app.application.worldData.generators.hydrology.load.hydrologyLocations import (
    geographic_locations,
)
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.dataModel.topology.topologyGeometry import canonical_frame
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.application.worldData.generators.hydrology.types import (
    HYDROLOGY_BOOTSTRAP_SCOPES,
    HydrologyMasterInput,
    HydrologyScope,
    LoadedConnectionGraph,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _grid_segments(segments: list[tuple[Coord, Coord]], map_cell: int,
                    topology: WorldTopology | None) -> list[tuple[Coord, Coord]]:
    projected = fine_segments_to_grid(segments, map_cell)
    if not projected or topology is None:
        return projected
    points = canonical_frame(topology, (point for segment in projected for point in segment),
                              anchor=projected[0][0])
    return list(zip(points[::2], points[1::2], strict=True))


def build_hydrology_master_input(
    world: World,
    locations: list[NamedLocation],
    nodes: list[ConnectionNode] | None = None,
    edges: list[ConnectionEdge] | None = None,
    *,
    scopes: frozenset[HydrologyScope] | None = None,
) -> HydrologyMasterInput:
    """Declared geometry on WORLD_SURFACE_GRID — coarse heightmap keys (gx, gy)."""
    _ = nodes, edges  # roads / future; hydrology declare no longer from graph
    declared = load_declared_hydrology(world, locations)
    map_cell = map_cell_fine_span(world)
    topology = resolve_hydrology_topology(world, locations=locations)
    active_scopes = scopes if scopes is not None else HYDROLOGY_BOOTSTRAP_SCOPES
    return HydrologyMasterInput(
        world_uid=world.world_uid,
        hydrology_enabled=is_hydrology_enabled(world),
        scopes=active_scopes,
        connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        geographic_locations=geographic_locations(locations),
        declared_coastline_specs=[replace(spec, segments=_grid_segments(spec.segments, map_cell, topology))
            for spec in declared.coastline_specs],
        declared_lake_specs=[
            replace(spec, shoreline_segments=_grid_segments(spec.shoreline_segments, map_cell, topology))
            for spec in declared.lake_specs
        ],
        declared_river_edges=[
            replace(edge, segment=_grid_segments([edge.segment], map_cell, topology)[0])
            for edge in declared.river_edges
        ],
        declared_river_intents=declared.river_intents,
        river_system_index=declared.river_system_index,
    )
