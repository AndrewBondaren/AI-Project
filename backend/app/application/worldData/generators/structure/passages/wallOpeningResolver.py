"""
Exterior wall profile computation for algorithmic window placement.
See tz_building_generator.md §3.10 Правило 2, §3.11.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.worldData.generators.structure.roomInstance import _RoomInstance

_DIR_DELTA: dict[str, tuple[int, int]] = {
    "north": (0, +1),
    "south": (0, -1),
    "east":  (+1, 0),
    "west":  (-1, 0),
}


@dataclass
class ExteriorWallProfile:
    z_height: int
    z_base: int
    # direction → available cells after adaptive corner cut (§3.10 Правило 2, steps 1-2)
    walls: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    @property
    def has_exterior_walls(self) -> bool:
        return any(bool(v) for v in self.walls.values())


def _exterior_cells(
    room: _RoomInstance,
    direction: str,
    all_fp: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    dx, dy = _DIR_DELTA[direction]
    fp = room.get_footprint()
    cells = [(x, y) for (x, y) in fp if (x + dx, y + dy) not in all_fp]
    if direction in ("north", "south"):
        cells.sort(key=lambda c: c[0])
    else:
        cells.sort(key=lambda c: c[1])
    return cells


def _adaptive_corner_cut(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    §3.10 Правило 2, step 2: adaptive corner exclusion.
    n ≤ 2 → skip; cut = clamp(n−3, 0, 2)
    """
    n = len(cells)
    if n <= 2:
        return []
    cut = max(0, min(2, n - 3))
    return cells[cut: n - cut] if cut > 0 else list(cells)


def compute_exterior_wall_profiles(
    rooms: list[_RoomInstance],
    all_fp: set[tuple[int, int]],
    z_base: int,
) -> dict[str, ExteriorWallProfile]:
    """
    For each placed non-shaft room, compute exterior wall available cells per direction.
    Returns mapping room.uid_key → ExteriorWallProfile.
    """
    profiles: dict[str, ExteriorWallProfile] = {}
    for room in rooms:
        if not room.placed or room.is_shaft:
            continue
        walls: dict[str, list[tuple[int, int]]] = {}
        for direction in ("north", "south", "east", "west"):
            cells = _adaptive_corner_cut(_exterior_cells(room, direction, all_fp))
            if cells:
                walls[direction] = cells
        profiles[room.uid_key] = ExteriorWallProfile(
            z_height=room.z_height,
            z_base=z_base,
            walls=walls,
        )
    return profiles
