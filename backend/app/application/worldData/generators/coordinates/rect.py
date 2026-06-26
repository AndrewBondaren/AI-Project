from app.db.models.namedLocation import NamedLocation

from app.application.worldData.generators.coordinates.convert import (
    grid_dimension,
    meters_to_grid_x,
    meters_to_grid_y,
    settlement_origin_m,
)
from app.application.worldData.generators.coordinates.types import (
    GridX,
    GridY,
    LocalMeterRect,
    MeterX,
    MeterY,
    SurfaceGridRect,
)


def settlement_grid_rect(
    settlement: NamedLocation,
    cell_m: int,
    side_m: int,
) -> SurfaceGridRect:
    """Footprint in world surface grid indices [gx0, gx1) × [gy0, gy1)."""
    origin = settlement_origin_m(settlement)
    n = grid_dimension(side_m, cell_m)
    gx0 = meters_to_grid_x(origin.x, cell_m)
    gy0 = meters_to_grid_y(origin.y, cell_m)
    return SurfaceGridRect(
        gx0=gx0,
        gy0=gy0,
        gx1=GridX(gx0 + n),
        gy1=GridY(gy0 + n),
    )


def settlement_meter_rect(
    settlement: NamedLocation,
    side_m: int,
) -> LocalMeterRect:
    """Footprint in world local meters [x0, x1) × [y0, y1) at ground z."""
    origin = settlement_origin_m(settlement)
    return LocalMeterRect(
        x0=origin.x,
        y0=origin.y,
        x1=MeterX(origin.x + side_m),
        y1=MeterY(origin.y + side_m),
        z=origin.z,
    )


def cell_in_surface_grid_rect(x: int, y: int, rect: SurfaceGridRect) -> bool:
    return rect.gx0 <= x < rect.gx1 and rect.gy0 <= y < rect.gy1


def cell_in_local_meter_rect(x: int, y: int, rect: LocalMeterRect) -> bool:
    return rect.x0 <= x < rect.x1 and rect.y0 <= y < rect.y1
