"""River grid IO and local turn frames use the shared topology domain."""

from collections import deque
from collections.abc import Collection, Iterable

from app.application.worldData.generators.hydrology.geom.smoothRiverPolyline import step_turn_ok
from app.dataModel.topology.topologyGeometry import canonical_neighbors8, unrolled_images
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def river_turn_ok(topology: WorldTopology, path: list[Coord], candidate: Coord) -> bool:
    if not isinstance(topology, WorldTopology):
        raise TypeError("river geometry requires an explicit WorldTopology")
    if len(path) < 2:
        return True
    current = path[-1]
    previous = unrolled_images(topology, path[-2], anchor=current)[0].coord
    following = unrolled_images(topology, candidate, anchor=current)[0].coord
    return step_turn_ok([previous, current], following)


def distance_to_mouths(topology: WorldTopology, cells: Collection[Coord],
                       mouths: Iterable[Coord]) -> dict[Coord, int]:
    """D8 graph distances, one multi-source traversal instead of per-cell scans."""
    if not isinstance(topology, WorldTopology):
        raise TypeError("river geometry requires an explicit WorldTopology")
    distances = {cell: 0 for cell in mouths if cell in cells}
    queue = deque(sorted(distances))
    while queue:
        cell = queue.popleft()
        for neighbor in canonical_neighbors8(topology, cell):
            if neighbor in cells and neighbor not in distances:
                distances[neighbor] = distances[cell] + 1
                queue.append(neighbor)
    return distances
