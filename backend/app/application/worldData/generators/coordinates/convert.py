from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

from app.application.worldData.generators.coordinates.types import (
    GridX,
    GridY,
    LocalMeterCoord,
    MeterX,
    MeterY,
    MeterZ,
)


def cell_size_m(world: World) -> int:
    map_settings = getattr(world, "map_settings", None) or {}
    if isinstance(map_settings, dict):
        val = map_settings.get("global_cell_size_m")
        if val is not None:
            return int(val)
    return int(world.map_cell_size_m or 3000)


def grid_dimension(side_m: int, cell_m: int) -> int:
    return max(1, round(side_m / cell_m))


def meters_to_grid_x(x: int, cell_m: int) -> GridX:
    return GridX(x // cell_m)


def meters_to_grid_y(y: int, cell_m: int) -> GridY:
    return GridY(y // cell_m)


def grid_tile_origin_x(gx: int, cell_m: int) -> MeterX:
    return MeterX(gx * cell_m)


def grid_tile_origin_y(gy: int, cell_m: int) -> MeterY:
    return MeterY(gy * cell_m)


def settlement_origin_m(settlement: NamedLocation) -> LocalMeterCoord:
    return LocalMeterCoord(
        x=MeterX(settlement.map_x if settlement.map_x is not None else 0),
        y=MeterY(settlement.map_y if settlement.map_y is not None else 0),
        z=MeterZ(settlement.map_z if settlement.map_z is not None else 0),
    )
