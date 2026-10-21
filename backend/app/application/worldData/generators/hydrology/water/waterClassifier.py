"""Physical classification: authored intent, ocean level/mass, world extent."""

from collections.abc import Sequence

from app.application.worldData.generators.hydrology.water.levelFill import LevelFill
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from app.dataModel.topology.worldTopology import WorldTopology


def classify_components(components: Sequence[LevelFill], levels: Sequence[int],
                        topology: WorldTopology, default_water_level: int,
                        policy: HydrologySeasPolicy,
                        authored: Sequence[BasinKind | None]) -> tuple[BasinKind, ...]:
    """World boundary is a signal; the edge of a partial bake is never used."""
    if len(components) != len(levels) or len(components) != len(authored):
        raise ValueError("water classification inputs must have equal lengths")
    candidates = [i for i, component in enumerate(components)
                  if component.cells and authored[i] is None and levels[i] == default_water_level]
    largest = max((components[i].area for i in candidates), default=0)
    world_area = topology.bounds.width * topology.bounds.height
    result = []
    for i, component in enumerate(components):
        if authored[i] is not None:
            result.append(authored[i])
            continue
        boundary = any(len(canonical_neighbors4(topology, cell)) < 4 for cell in component.cells)
        if i in candidates and (component.area == largest or boundary):
            result.append(BasinKind.OCEAN)
        elif component.area / world_area >= policy.inland_sea_min_area_fraction:
            result.append(BasinKind.INLAND_SEA)
        else:
            result.append(BasinKind.LAKE)
    return tuple(result)
