"""Declare river / mountain_river edges — D HY-4."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.types import (
    DeclaredRiverEdge,
    LoadedConnectionGraph,
)
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType

_RIVER_TYPES = frozenset({
    HydrologyConnectionType.RIVER,
    HydrologyConnectionType.MOUNTAIN_RIVER,
})


def _location_uid_for_edge(
    from_uid: str,
    to_uid: str,
    graph: LoadedConnectionGraph,
) -> str | None:
    nodes = {n.node_uid: n for n in graph.nodes}
    for uid in (from_uid, to_uid):
        node = nodes.get(uid)
        if node is not None and node.location_uid:
            return node.location_uid
    return None


def extract_declared_river_edges(graph: LoadedConnectionGraph) -> list[DeclaredRiverEdge]:
    nodes_by_uid = {node.node_uid: node for node in graph.nodes}
    declared: list[DeclaredRiverEdge] = []
    for edge in graph.edges:
        ctype = HydrologyConnectionType.from_wire(edge.get("connection_type"))
        if ctype not in _RIVER_TYPES:
            continue
        from_node = nodes_by_uid.get(edge.get("from_node_uid", ""))
        to_node = nodes_by_uid.get(edge.get("to_node_uid", ""))
        if from_node is None or to_node is None:
            continue
        width = edge.get("width_cells")
        declared.append(DeclaredRiverEdge(
            edge_uid=str(edge.get("edge_uid", "")),
            segment=((from_node.gx, from_node.gy), (to_node.gx, to_node.gy)),
            connection_type=ctype.value,
            width_cells=int(width) if width is not None else 1,
            location_uid=_location_uid_for_edge(
                edge.get("from_node_uid", ""),
                edge.get("to_node_uid", ""),
                graph,
            ),
        ))
    return declared
