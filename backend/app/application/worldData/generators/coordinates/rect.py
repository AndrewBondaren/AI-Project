from app.db.models.namedLocation import NamedLocation

from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_x,
    fine_to_grid_y,
    grid_dimension,
    settlement_origin_fine,
)
from app.application.worldData.generators.coordinates.types import (
    FineGridRect,
    FineX,
    FineY,
    GridX,
    GridY,
    SurfaceGridRect,
)


def settlement_grid_rect(
    settlement: NamedLocation,
    map_cell: int,
    side_fine: int,
) -> SurfaceGridRect:
    """Footprint in world surface grid indices [gx0, gx1) × [gy0, gy1)."""
    origin = settlement_origin_fine(settlement)
    n = grid_dimension(side_fine, map_cell)
    gx0 = fine_to_grid_x(origin.x, map_cell)
    gy0 = fine_to_grid_y(origin.y, map_cell)
    return SurfaceGridRect(
        gx0=gx0,
        gy0=gy0,
        gx1=GridX(gx0 + n),
        gy1=GridY(gy0 + n),
    )


def settlement_fine_rect(
    settlement: NamedLocation,
    side_fine: int,
) -> FineGridRect:
    """Footprint in world fine grid [x0, x1) × [y0, y1) at ground z."""
    origin = settlement_origin_fine(settlement)
    return FineGridRect(
        x0=origin.x,
        y0=origin.y,
        x1=FineX(origin.x + side_fine),
        y1=FineY(origin.y + side_fine),
        z=origin.z,
    )


def cell_in_surface_grid_rect(x: int, y: int, rect: SurfaceGridRect) -> bool:
    return rect.gx0 <= x < rect.gx1 and rect.gy0 <= y < rect.gy1


def cell_in_fine_rect(x: int, y: int, rect: FineGridRect) -> bool:
    return rect.x0 <= x < rect.x1 and rect.y0 <= y < rect.y1
