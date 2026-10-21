"""Receiving water is resolved body extent, never a global height threshold."""

from collections.abc import Mapping

from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.topology.worldTopology import Coord


def is_river_mouth(cell: Coord, surface_z: Mapping[Coord, int],
                   occupied: Mapping[Coord, MapCellHydrology]) -> bool:
    entry = occupied.get(cell)
    if entry is None:
        return False
    if entry.role is not None and entry.role.is_open_water_role():
        return True
    return (entry.water_body_uid is not None and entry.z_water_level is not None
            and cell in surface_z and surface_z[cell] < entry.z_water_level)
