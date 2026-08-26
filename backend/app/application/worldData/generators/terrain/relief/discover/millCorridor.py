"""Live SLOPE corridor: occ on vertices or committed front traces.

Mill always passes ``LiveCorridors``. Tests may use ``CellSetCorridor``.
SoT: ``docs/tz_terrain_relief.md`` C41 / R41 T-21.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    FrontGeometry,
)


class CorridorLive(Protocol):
    """Whether ``xy`` is a SLOPE corridor cell right now, and which bake slot owns it."""

    def is_corridor(self, xy: Coord) -> bool: ...
    def owner_slot(self, xy: Coord) -> int | None: ...


@dataclass(frozen=True, slots=True)
class LiveCorridors:
    """Wraps the mill ``fronts`` list (same object the stank appends to)."""

    fronts: list[FrontGeometry]

    def is_corridor(self, xy: Coord) -> bool:
        return any(xy in item.corridor for item in self.fronts)

    def owner_slot(self, xy: Coord) -> int | None:
        for item in self.fronts:
            if xy in item.corridor:
                return int(item.slot)
        return None


@dataclass(frozen=True, slots=True)
class CellSetCorridor:
    """Test double: explicit corridor cells, optional slot map."""

    cells: frozenset[Coord]
    slots: Mapping[Coord, int] | None = None

    def is_corridor(self, xy: Coord) -> bool:
        return xy in self.cells

    def owner_slot(self, xy: Coord) -> int | None:
        if self.slots is None:
            return None
        slot = self.slots.get(xy)
        return None if slot is None else int(slot)


def corridor_from_cells(
    cells: Sequence[Coord] | set[Coord],
    slots: Mapping[Coord, int] | None = None,
) -> CellSetCorridor:
    return CellSetCorridor(cells=frozenset(cells), slots=slots)
