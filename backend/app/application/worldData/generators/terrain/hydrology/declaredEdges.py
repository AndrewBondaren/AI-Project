"""Coastline edge extraction from loaded connection graph — D HY-2."""

from __future__ import annotations

from app.application.worldData.generators.terrain.hydrology.types import LoadedConnectionGraph
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType


def extract_declared_segments(
    graph: LoadedConnectionGraph,
    connection_type: HydrologyConnectionType,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    nodes_by_uid = {node.node_uid: node for node in graph.nodes}
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for edge in graph.edges:
        if HydrologyConnectionType.from_wire(edge.get("connection_type")) != connection_type:
            continue
        from_node = nodes_by_uid.get(edge.get("from_node_uid", ""))
        to_node = nodes_by_uid.get(edge.get("to_node_uid", ""))
        if from_node is None or to_node is None:
            continue
        segments.append(
            ((from_node.gx, from_node.gy), (to_node.gx, to_node.gy)),
        )
    return segments
