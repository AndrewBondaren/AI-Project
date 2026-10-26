"""Multi-source BFS distance from the footprint boundary (HY-12 step 3a)."""

from collections import deque

from app.dataModel.topology import topologyGeometry as geometry
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def distance_from_boundary(cells: frozenset[Coord], topology: WorldTopology) -> dict[Coord, int]:
    """d=1 on cells touching the outside; propagate inward; {} if no boundary."""
    dist: dict[Coord, int] = {}
    queue = deque(
        cell for cell in sorted(cells)
        if any(neighbor not in cells
               for neighbor in geometry.canonical_neighbors4(topology, cell))
    )
    for cell in queue:
        dist[cell] = 1
    while queue:
        cell = queue.popleft()
        for neighbor in geometry.canonical_neighbors4(topology, cell):
            if neighbor in cells and neighbor not in dist:
                dist[neighbor] = dist[cell] + 1
                queue.append(neighbor)
    return dist
