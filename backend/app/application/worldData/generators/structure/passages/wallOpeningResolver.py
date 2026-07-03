"""
Exterior wall profile computation for algorithmic window placement.
See tz_building_generator.md §3.10 Правило 2, §3.11.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.dataModel.spatial.facing import (
    CARDINAL_FACINGS,
    CARDINAL_WALL_OUTWARD_DELTA,
    Facing,
    is_meridional_edge,
)
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance


@dataclass
class ExteriorWallProfile:
    z_height: int
    z_base: int
    # wire facing → available cells after adaptive corner cut (§3.10 Правило 2, steps 1-2)
    walls: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    @property
    def has_exterior_walls(self) -> bool:
        return any(bool(v) for v in self.walls.values())


def _exterior_cells(
    room: _RoomInstance,
    facing: Facing,
    all_fp: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
    fp = room.get_footprint()
    cells = [(x, y) for (x, y) in fp if (x + dx, y + dy) not in all_fp]
    if is_meridional_edge(facing):
        cells.sort(key=lambda c: c[0])
    else:
        cells.sort(key=lambda c: c[1])
    return cells


def _corner_cut(cells: list[tuple[int, int]], cut: int) -> list[tuple[int, int]]:
    n = len(cells)
    if n <= 2:
        return []
    return cells[cut: n - cut] if cut > 0 else list(cells)


def _adaptive_corner_cut(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """§3.10 Правило 2, step 2: cut = clamp(n−3, 0, 2)"""
    return _corner_cut(cells, max(0, min(2, len(cells) - 3)))


def compute_exterior_wall_profiles(
    rooms: list[_RoomInstance],
    all_fp: set[tuple[int, int]],
    z_base: int,
) -> dict[str, ExteriorWallProfile]:
    profiles: dict[str, ExteriorWallProfile] = {}
    for room in rooms:
        if not room.placed:
            continue
        walls: dict[str, list[tuple[int, int]]] = {}
        for facing in CARDINAL_FACINGS:
            raw = _exterior_cells(room, facing, all_fp)
            cells = _corner_cut(raw, 1) if room.is_shaft else _adaptive_corner_cut(raw)
            if cells:
                walls[facing.value] = cells
        profiles[room.uid_key] = ExteriorWallProfile(
            z_height=room.z_height,
            z_base=z_base,
            walls=walls,
        )
    return profiles
