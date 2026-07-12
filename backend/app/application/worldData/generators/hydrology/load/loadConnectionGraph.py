"""Load connection graph from DB models — D HY-0c."""

from __future__ import annotations

from dataclasses import asdict

from app.application.worldData.generators.coordinates.convert import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.application.worldData.generators.hydrology.types import (
    LoadedConnectionGraph,
    ResolvedConnectionNode,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _resolve_node_meters(
    node: ConnectionNode,
    locations_by_uid: dict[str, NamedLocation],
) -> tuple[int, int, int]:
    if node.location_uid and node.location_uid in locations_by_uid:
        loc = locations_by_uid[node.location_uid]
        x = loc.map_x if loc.map_x is not None else node.x
        y = loc.map_y if loc.map_y is not None else node.y
        z = loc.map_z if loc.map_z is not None else node.z
        return int(x), int(y), int(z)
    return int(node.x), int(node.y), int(node.z)


def load_connection_graph(
    world: World,
    locations: list[NamedLocation],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> LoadedConnectionGraph:
    """Resolve waypoint coords (meters) and grid indices for hydrology."""
    loc_map = {loc.location_uid: loc for loc in locations}
    cell_m = cell_size_m(world)

    resolved: list[ResolvedConnectionNode] = []
    for node in nodes:
        x_m, y_m, z_m = _resolve_node_meters(node, loc_map)
        resolved.append(ResolvedConnectionNode(
            node_uid=node.node_uid,
            x_m=x_m,
            y_m=y_m,
            z_m=z_m,
            gx=int(meters_to_grid_x(x_m, cell_m)),
            gy=int(meters_to_grid_y(y_m, cell_m)),
            node_type=node.node_type,
            graph_level=node.graph_level,
            location_uid=node.location_uid,
        ))

    edge_dicts = [asdict(e) for e in edges]
    return LoadedConnectionGraph(nodes=resolved, edges=edge_dicts)


def load_connection_graph_from_rows(
    world: World,
    locations: list[NamedLocation],
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> LoadedConnectionGraph:
    return load_connection_graph(world, locations, nodes, edges)
