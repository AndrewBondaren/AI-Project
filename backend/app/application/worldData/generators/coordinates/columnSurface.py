"""Column max-z and median surface sample — C21 / assembler §6.2.

Does not choose which cells belong to a threshold or yard.
"""

from __future__ import annotations

from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation

Coord = tuple[int, int]


def column_surface(terrain_cells: list[MapCell] | None) -> dict[Coord, int]:
    """``(x, y) → max z`` in the column. Empty / None → ``{}``."""
    if not terrain_cells:
        return {}
    surface: dict[Coord, int] = {}
    for cell in terrain_cells:
        key = (cell.x, cell.y)
        z = int(cell.z)
        prev = surface.get(key)
        if prev is None or z > prev:
            surface[key] = z
    return surface


def median_surface_z(
    cells: list[Coord],
    surface: dict[Coord, int],
    fallback: int,
) -> int:
    zs = sorted(surface[xy] for xy in cells if xy in surface)
    if not zs:
        return int(fallback)
    return zs[len(zs) // 2]


def resolve_district_pin_z(
    settlement: NamedLocation,
    origin_x: int,
    origin_y: int,
    surface: dict[Coord, int],
) -> int:
    """Coarse district pin: surface at origin, not max AABB."""
    fallback = settlement.map_z if settlement.map_z is not None else 0
    return int(surface.get((int(origin_x), int(origin_y)), fallback))
