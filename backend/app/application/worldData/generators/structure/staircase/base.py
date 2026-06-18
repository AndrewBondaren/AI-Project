"""
Base staircase builder. Each type inherits and implements build().
"""
import logging
from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.cellBuilder import _interior
from app.application.worldData.generators.structure.cellFactory import _floor_cell, _void_cell
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

# Всё что НЕ является проходимым — блокирует просвет над лестницей.
_PASSABLE_ELEMENTS = {"archway", "void"}

# Ячейки шахты, над которыми проверяется просвет.
_STAIR_ELEMENTS = {"staircase", "stair_anchor", "stair_floor"}


def _blocks_headroom(elem: str) -> bool:
    return elem not in _PASSABLE_ELEMENTS


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
            if above is not None and _blocks_headroom(above.system_building_element):
                raise ValueError(
                    f"staircase {conn_label!r}: headroom blocked at "
                    f"({x},{y},z={z_check}) by {above.system_building_element!r}"
                )


def check_all_stair_headrooms(cells: dict, clearance: int = 2) -> None:
    """
    Постпроверка после того как все марши построены.
    Проверяет все ячейки шахты — нет ли блокера на clearance уровней выше.
    Блокером считается всё кроме archway и void.
    """
    for (x, y, z), cell in cells.items():
        if cell.system_building_element not in _STAIR_ELEMENTS:
            continue
        for dz in range(1, clearance + 1):
            above = cells.get((x, y, z + dz))
            if above is not None and _blocks_headroom(above.system_building_element):
                logger.error(
                    "headroom | (%d,%d,z=%d) %s blocked at z=%d by %r",
                    x, y, z, cell.system_building_element, z + dz,
                    above.system_building_element,
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
        sc_entry: dict | None = None,
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
        self.shaft           = shaft       # shaft instance (new schema); None = old schema
        self.sc_entry        = sc_entry    # raw staircases[] entry; None = old schema
        self.z_height        = abs(to_level.z - fr_level.z)
        self.z_lo            = min(fr_level.z, to_level.z)
        self.z_top           = max(fr_level.z, to_level.z)
        self.path_set: set[tuple[int, int, int]] = set()
        self._is_first_flight: bool = True

    @abstractmethod
    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """Places stair cells, sets self.path_set. Returns (fr_anchor, to_anchor)."""

    def clear_shaft(self) -> None:
        """All shaft interior cells not in path_set → void."""
        if self.shaft is None:
            return
        interior = set(_interior(self.shaft.get_footprint()))
        for z in range(self.z_lo, self.z_top + 1):
            for (x, y) in interior:
                if (x, y, z) not in self.path_set:
                    self.cells[(x, y, z)] = _void_cell(x, y, z, self.world_uid, self.building_uid)

    def lay_base_floor(self) -> None:
        """void → floor at z_lo (first flight only)."""
        if not self._is_first_flight or self.shaft is None:
            return
        for (x, y) in _interior(self.shaft.get_footprint()):
            c = self.cells.get((x, y, self.z_lo))
            if c is not None and c.system_building_element == "void":
                self.cells[(x, y, self.z_lo)] = _floor_cell(
                    x, y, self.z_lo, self.world_uid, self.building_uid, self.mat
                )
