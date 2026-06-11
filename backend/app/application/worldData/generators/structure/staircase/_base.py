"""
Base staircase builder. Each type inherits and implements build().
"""
from abc import ABC, abstractmethod

from app.application.worldData.generators.structure._cellBuilder import _interior
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell

_SOLID_ELEMENTS = {"wall", "floor", "column", "staircase_base"}


def sw_anchor(room: _RoomInstance) -> tuple[int, int]:
    """SW-угол interior комнаты — детерминированный якорь."""
    interior = list(_interior(room.get_footprint()))
    if not interior:
        interior = list(room.get_footprint())
    xs = [x for x, _ in interior]
    ys = [y for _, y in interior]
    return (min(xs), min(ys))


def check_headroom(
    path_cells: list[tuple[int, int, int]],
    cells: dict,
    conn_label: str,
    clearance: int,
    z_lo: int,
    z_top: int,
) -> None:
    for (x, y, z) in path_cells:
        for dz in range(1, clearance + 1):
            z_check = z + dz
            if z_check > z_top:
                continue
            above = cells.get((x, y, z_check))
            if above is not None and above.system_building_element in _SOLID_ELEMENTS:
                raise ValueError(
                    f"staircase {conn_label!r}: headroom blocked at "
                    f"({x},{y},z={z_check}) by {above.system_building_element!r}"
                )


class StaircaseBuilder(ABC):
    def __init__(
        self,
        fr: _RoomInstance,
        to: _RoomInstance,
        fr_level: LocationLevel,
        to_level: LocationLevel,
        cells: dict[tuple, MapCell],
        world_uid: str,
        building_uid: str,
        mat: str,
        conn_label: str,
        shaft: _RoomInstance | None = None,
    ) -> None:
        self.fr           = fr
        self.to           = to
        self.fr_level     = fr_level
        self.to_level     = to_level
        self.cells        = cells
        self.world_uid    = world_uid
        self.building_uid = building_uid
        self.mat          = mat
        self.conn_label   = conn_label
        self.shaft        = shaft       # shaft instance (new schema); None = old schema
        self.z_height     = abs(to_level.z - fr_level.z)
        self.z_lo         = min(fr_level.z, to_level.z)
        self.z_top        = max(fr_level.z, to_level.z)

    @abstractmethod
    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """Returns (fr_anchor, to_anchor)."""
