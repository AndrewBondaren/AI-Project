"""Deterministic four-connected components on the canonical working grid."""

from collections import deque
from collections.abc import Iterable, Mapping

from app.application.worldData.generators.hydrology.water.levelFill import LevelFill

from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def component_label(cells: Iterable[Coord], topology: WorldTopology) -> tuple[frozenset[Coord], ...]:
    return tuple(component.cells for component in _label(cells, topology, None))


def component_fills(cells: Iterable[Coord], topology: WorldTopology,
                     surface_z: Mapping[Coord, int]) -> tuple[LevelFill, ...]:
    return _label(cells, topology, surface_z)


def _label(cells: Iterable[Coord], topology: WorldTopology,
           surface_z: Mapping[Coord, int] | None) -> tuple[LevelFill, ...]:
    remaining = set(cells)
    components = []
    for seed in sorted(remaining, key=lambda xy: (xy[1], xy[0])):
        if seed not in remaining:
            continue
        remaining.remove(seed)
        queue = deque([seed])
        component = {seed}
        floor = None
        while queue:
            cell = queue.popleft()
            if surface_z is not None:
                floor = surface_z[cell] if floor is None else min(floor, surface_z[cell])
            for neighbor in canonical_neighbors4(topology, cell):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(LevelFill(frozenset(component), floor))
    return tuple(components)
