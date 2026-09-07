from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

from app.application.worldData.generators.coordinates.types import (
    FineDelta,
    FineGridCoord,
    FineX,
    FineY,
    FineZ,
    GridX,
    GridY,
)


def map_cell_fine_span(world: World) -> int:
    map_settings = getattr(world, "map_settings", None) or {}
    if isinstance(map_settings, dict):
        val = map_settings.get("global_cell_size_m")
        if val is not None:
            return int(val)
    v = world.fine_cells_per_map_cell
    if v is None:
        raise ValueError(
            f"world {getattr(world, 'world_uid', '?')} missing fine_cells_per_map_cell"
        )
    return int(v)


def grid_dimension(side_fine: int, map_cell: int) -> int:
    return max(1, round(side_fine / map_cell))


def fine_to_grid_x(x: int, map_cell: int) -> GridX:
    return GridX(x // map_cell)


def fine_to_grid_y(y: int, map_cell: int) -> GridY:
    return GridY(y // map_cell)


def grid_tile_origin_x(gx: int, map_cell: int) -> FineX:
    return FineX(gx * map_cell)


def grid_tile_origin_y(gy: int, map_cell: int) -> FineY:
    return FineY(gy * map_cell)


def settlement_origin_fine(settlement: NamedLocation) -> FineGridCoord:
    return FineGridCoord(
        x=FineX(settlement.map_x if settlement.map_x is not None else 0),
        y=FineY(settlement.map_y if settlement.map_y is not None else 0),
        z=FineZ(settlement.map_z if settlement.map_z is not None else 0),
    )


def coarse_tile_offset_fine(tile_index: int, map_cell: int) -> FineDelta:
    """Offset in WORLD_FINE_GRID for tile_index steps on coarse surface grid."""
    return FineDelta(tile_index * map_cell)


def coarse_cell_fine_xy(
    origin: FineGridCoord,
    cell_x: int,
    cell_y: int,
    map_cell: int,
) -> tuple[FineX, FineY]:
    """Origin of coarse grid cell (cell_x, cell_y) relative to settlement anchor."""
    return (
        FineX(origin.x + coarse_tile_offset_fine(cell_x, map_cell)),
        FineY(origin.y + coarse_tile_offset_fine(cell_y, map_cell)),
    )
