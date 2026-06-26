"""Terrain helpers for district placement (ground_z, adjacency)."""

from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation


def resolve_ground_z(
    settlement:    NamedLocation,
    origin_x:      int,
    origin_y:      int,
    width_m:       int,
    depth_m:       int,
    terrain_cells: list[MapCell] | None,
) -> int:
    """
    ground_z района: max z terrain-ячеек внутри footprint слота;
    fallback — settlement.map_z (или 0).
    """
    fallback = settlement.map_z if settlement.map_z is not None else 0
    if not terrain_cells:
        return fallback

    x1 = origin_x + width_m
    y1 = origin_y + depth_m
    zs = [
        cell.z
        for cell in terrain_cells
        if origin_x <= cell.x < x1 and origin_y <= cell.y < y1
    ]
    if not zs:
        return fallback
    return max(zs)
