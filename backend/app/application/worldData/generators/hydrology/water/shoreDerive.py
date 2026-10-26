"""Dry shores derived from final water, including the strict waterline."""

from collections.abc import Mapping

from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.topology.topologyGeometry import canonical_neighbors4
from app.dataModel.topology.worldTopology import Coord, WorldTopology


def derive_shore(surface_z: Mapping[Coord, int], water: Mapping[Coord, MapCellHydrology],
                 topology: WorldTopology) -> dict[Coord, MapCellHydrology]:
    result: dict[Coord, MapCellHydrology] = {}
    # Source identity then canonical cell order decides shared dry-shore ownership.
    for cell, entry in sorted(water.items(), key=lambda item: (
        item[1].water_body_uid or "", item[0][1], item[0][0],
    )):
        kind = HydrologyShoreKind.for_open_water_role(entry.role)
        if kind is None or entry.z_water_level is None:
            continue
        for neighbor in canonical_neighbors4(topology, cell):
            if neighbor not in surface_z:
                raise ValueError(f"unresolved shore: missing elevation at {neighbor}")
            if neighbor in water or neighbor in result:
                continue
            if surface_z[neighbor] < entry.z_water_level:
                raise ValueError(f"incomplete level fill next to {cell}: {neighbor}")
            result[neighbor] = MapCellHydrology.shore(
                kind, water_body_uid=entry.water_body_uid,
            ).with_water_level(entry.z_water_level)
    return result
