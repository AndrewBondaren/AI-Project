"""
Base staircase builder. Each type inherits and implements build().
"""
import logging
from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.cellBuilder import _interior, _wall_cell
from app.application.worldData.generators.structure.cellFactory import _floor_cell, _void_cell, _window_cell
from app.application.worldData.generators.structure.heightChecker import PassageHeightChecker
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.structureElement import StructureElement
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)


def sw_anchor(room: _RoomInstance) -> tuple[int, int]:
    """SW-угол interior комнаты — детерминированный якорь."""
    interior = list(_interior(room.get_footprint()))
    if not interior:
        interior = list(room.get_footprint())
    xs = [x for x, _ in interior]
    ys = [y for _, y in interior]
    return (min(xs), min(ys))


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
        *,
        shaft: _RoomInstance | None = None,
        sc_entry: dict | None = None,
        passage_height: int,
    ) -> None:
        # Нормализация: fr = нижняя комната (меньший z), to = верхняя
        if fr_level.z > to_level.z:
            fr, to = to, fr
            fr_level, to_level = to_level, fr_level

        self.fr           = fr
        self.to           = to
        self.fr_level     = fr_level
        self.to_level     = to_level
        self.cells        = cells
        self.world_uid    = world_uid
        self.building_uid = building_uid
        self.mat          = mat
        self.conn_label   = conn_label
        self.shaft           = shaft          # shaft instance (new schema); None = old schema
        self.sc_entry        = sc_entry       # raw staircases[] entry; None = old schema
        self.passage_height  = passage_height
        self.z_height        = abs(to_level.z - fr_level.z)
        self.z_lo            = min(fr_level.z, to_level.z)
        self.z_top           = max(fr_level.z, to_level.z)
        self.path_set: set[tuple[int, int, int]] = set()
        self._is_first_flight: bool = True
        self.extra_passages: list = []
        self.skip_edge_ladder: bool = False

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

    def _shaft_neighbors(self, shaft_interior: set[tuple[int, int]]) -> list[tuple[int, int]]:
        return list({
            (ax + dx, ay + dy)
            for ax, ay in shaft_interior
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
            and (ax + dx, ay + dy) not in shaft_interior
        })

    def _place_shaft_enclosure(
        self,
        shaft_interior: set[tuple[int, int]],
        open_wall_shaft: str | None = None,
    ) -> None:
        shaft_height = self.z_top - self.z_lo
        checker = PassageHeightChecker(self.cells, self.passage_height)
        actual_height = checker.resolve_height(
            self._shaft_neighbors(shaft_interior), self.z_lo, shaft_height,
        )
        if actual_height is None:
            logger.warning(
                "shaft_enclosure %s: не удалось разместить стены — нет подходящей высоты",
                self.conn_label,
            )
            return
        if actual_height < shaft_height:
            logger.warning(
                "shaft_enclosure %s: высота уменьшена %d→%d",
                self.conn_label, shaft_height, actual_height,
            )
        z_hi = self.z_lo + actual_height
        for ax, ay in shaft_interior:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    wx, wy = ax + dx, ay + dy
                    if (wx, wy) in shaft_interior:
                        continue
                    for z in range(self.z_lo, z_hi):
                        if (wx, wy, z) not in self.cells:
                            if open_wall_shaft:
                                self.cells[(wx, wy, z)] = _window_cell(
                                    wx, wy, z, self.world_uid, self.building_uid, open_wall_shaft,
                                )
                            else:
                                self.cells[(wx, wy, z)] = _wall_cell(
                                    wx, wy, z, self.world_uid, self.building_uid, self.mat,
                                )
        if actual_height < shaft_height:
            for ax, ay in shaft_interior:
                if (ax, ay, z_hi) not in self.cells:
                    self.cells[(ax, ay, z_hi)] = _wall_cell(
                        ax, ay, z_hi, self.world_uid, self.building_uid, self.mat,
                    )

    def _place_shaft_enclosure_closed(
        self,
        shaft_interior: set[tuple[int, int]],
        z_hi: int,
        open_wall_shaft: str | None = None,
    ) -> None:
        self._place_shaft_enclosure(shaft_interior, open_wall_shaft=open_wall_shaft)
        ext_height = z_hi - self.z_top
        if ext_height <= 0:
            return
        checker = PassageHeightChecker(self.cells, self.passage_height)
        actual_ext = checker.resolve_height(
            self._shaft_neighbors(shaft_interior), self.z_top, ext_height,
        )
        if actual_ext is None:
            logger.warning(
                "shaft_enclosure_closed %s: не удалось расширить стены выше z_top — пропускаем",
                self.conn_label,
            )
            return
        if actual_ext < ext_height:
            logger.warning(
                "shaft_enclosure_closed %s: расширение уменьшено %d→%d",
                self.conn_label, ext_height, actual_ext,
            )
        z_ceiling = self.z_top + actual_ext
        for ax, ay in shaft_interior:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    wx, wy = ax + dx, ay + dy
                    if (wx, wy) in shaft_interior:
                        continue
                    for z in range(self.z_top, z_ceiling + 1):
                        if (wx, wy, z) not in self.cells:
                            self.cells[(wx, wy, z)] = _wall_cell(
                                wx, wy, z, self.world_uid, self.building_uid, self.mat,
                            )
        for ax, ay in shaft_interior:
            if (ax, ay, z_ceiling) not in self.cells:
                self.cells[(ax, ay, z_ceiling)] = _floor_cell(
                    ax, ay, z_ceiling, self.world_uid, self.building_uid, self.mat,
                )

    def lay_base_floor(self) -> None:
        """void → floor at z_lo (first flight only)."""
        if not self._is_first_flight or self.shaft is None:
            return
        for (x, y) in _interior(self.shaft.get_footprint()):
            c = self.cells.get((x, y, self.z_lo))
            if c is not None and c.system_building_element == StructureElement.VOID:
                self.cells[(x, y, self.z_lo)] = _floor_cell(
                    x, y, self.z_lo, self.world_uid, self.building_uid, self.mat
                )
