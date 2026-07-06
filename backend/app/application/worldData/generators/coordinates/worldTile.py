"""World macro tile ↔ fine meter grid — map_cell_size_m local map."""

from __future__ import annotations

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.types import GridX, GridY, MeterX, MeterY
from app.application.worldData.generators.terrain.types import ColumnRect


def tile_index_x(x_m: int, cell_m: int) -> GridX:
    """World meter x → macro tile index."""
    return GridX(x_m // cell_m)


def tile_index_y(y_m: int, cell_m: int) -> GridY:
    return GridY(y_m // cell_m)


def local_index_x(x_m: int, cell_m: int) -> int:
    """Meter x → 0..cell_m-1 within tile (Python % for negatives)."""
    return x_m % cell_m


def local_index_y(y_m: int, cell_m: int) -> int:
    return y_m % cell_m


def tile_origin_x(gx: int, cell_m: int) -> int:
    return gx * cell_m


def tile_origin_y(gy: int, cell_m: int) -> int:
    return gy * cell_m


def world_meter_xy(gx: int, gy: int, lx: int, ly: int, cell_m: int) -> tuple[int, int]:
    return gx * cell_m + lx, gy * cell_m + ly


def macro_tile_of(x_m: int, y_m: int, cell_m: int) -> tuple[int, int]:
    return x_m // cell_m, y_m // cell_m


def iter_macro_tiles(bbox: GridBBox):
    """Macro tile indices covering GridBBox (tile index space)."""
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            yield gx, gy


def meter_bbox_for_tile(gx: int, gy: int, cell_m: int) -> GridBBox:
    x0 = tile_origin_x(gx, cell_m)
    y0 = tile_origin_y(gy, cell_m)
    return GridBBox(
        x_min=x0,
        x_max=x0 + cell_m - 1,
        y_min=y0,
        y_max=y0 + cell_m - 1,
    )


def macro_bbox_to_meter_bbox(macro: GridBBox, cell_m: int) -> GridBBox:
    return GridBBox(
        x_min=tile_origin_x(macro.x_min, cell_m),
        x_max=tile_origin_x(macro.x_max, cell_m) + cell_m - 1,
        y_min=tile_origin_y(macro.y_min, cell_m),
        y_max=tile_origin_y(macro.y_max, cell_m) + cell_m - 1,
    )


def iter_meter_chunks(meter_bbox: GridBBox, chunk_size: int):
    """Fine-meter ColumnRect chunks (row-major)."""
    for y0 in range(meter_bbox.y_min, meter_bbox.y_max + 1, chunk_size):
        for x0 in range(meter_bbox.x_min, meter_bbox.x_max + 1, chunk_size):
            yield ColumnRect(
                x_min=x0,
                x_max=min(x0 + chunk_size - 1, meter_bbox.x_max),
                y_min=y0,
                y_max=min(y0 + chunk_size - 1, meter_bbox.y_max),
            )


def expand_coarse_hydro_to_tile(
    coarse_by_cell: dict[tuple[int, int], object],
    tile_gx: int,
    tile_gy: int,
    cell_m: int,
) -> dict[tuple[int, int], object]:
    """Copy coarse (Gx,Gy) hydrology to every fine meter cell in tile."""
    entry = coarse_by_cell.get((tile_gx, tile_gy))
    if entry is None:
        return {}
    x0 = tile_origin_x(tile_gx, cell_m)
    y0 = tile_origin_y(tile_gy, cell_m)
    out: dict[tuple[int, int], object] = {}
    for ly in range(cell_m):
        for lx in range(cell_m):
            out[(x0 + lx, y0 + ly)] = entry
    return out


def is_macro_grid_coord(x: int, y: int, cell_m: int) -> bool:
    """Legacy occupancy: small indices stored as macro tile (pre-fine migration)."""
    if abs(x) >= cell_m or abs(y) >= cell_m:
        return False
    if abs(x) > 512 or abs(y) > 512:
        return False
    return True
