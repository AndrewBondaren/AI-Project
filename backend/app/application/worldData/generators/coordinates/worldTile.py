"""World macro tile ↔ fine grid — fine_cells_per_map_cell local map."""

from __future__ import annotations

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.types import GridX, GridY
from app.application.worldData.generators.terrain.types import ColumnRect


def tile_index_x(x_fine: int, map_cell: int) -> GridX:
    """World fine x → macro tile index."""
    return GridX(x_fine // map_cell)


def tile_index_y(y_fine: int, map_cell: int) -> GridY:
    return GridY(y_fine // map_cell)


def local_index_x(x_fine: int, map_cell: int) -> int:
    """Fine x → 0..map_cell-1 within tile (Python % for negatives)."""
    return x_fine % map_cell


def local_index_y(y_fine: int, map_cell: int) -> int:
    return y_fine % map_cell


def tile_origin_x(gx: int, map_cell: int) -> int:
    return gx * map_cell


def tile_origin_y(gy: int, map_cell: int) -> int:
    return gy * map_cell


def world_fine_xy(gx: int, gy: int, lx: int, ly: int, map_cell: int) -> tuple[int, int]:
    return gx * map_cell + lx, gy * map_cell + ly


def macro_tile_of(x_fine: int, y_fine: int, map_cell: int) -> tuple[int, int]:
    return x_fine // map_cell, y_fine // map_cell


def iter_macro_tiles(bbox: GridBBox):
    """Macro tile indices covering GridBBox (tile index space)."""
    for gy in range(bbox.y_min, bbox.y_max + 1):
        for gx in range(bbox.x_min, bbox.x_max + 1):
            yield gx, gy


def fine_bbox_for_tile(gx: int, gy: int, map_cell: int) -> GridBBox:
    x0 = tile_origin_x(gx, map_cell)
    y0 = tile_origin_y(gy, map_cell)
    return GridBBox(
        x_min=x0,
        x_max=x0 + map_cell - 1,
        y_min=y0,
        y_max=y0 + map_cell - 1,
    )


def macro_bbox_to_fine_bbox(macro: GridBBox, map_cell: int) -> GridBBox:
    return GridBBox(
        x_min=tile_origin_x(macro.x_min, map_cell),
        x_max=tile_origin_x(macro.x_max, map_cell) + map_cell - 1,
        y_min=tile_origin_y(macro.y_min, map_cell),
        y_max=tile_origin_y(macro.y_max, map_cell) + map_cell - 1,
    )


def iter_fine_chunks(fine_bbox: GridBBox, chunk_size: int):
    """Fine-grid ColumnRect chunks (row-major)."""
    for y0 in range(fine_bbox.y_min, fine_bbox.y_max + 1, chunk_size):
        for x0 in range(fine_bbox.x_min, fine_bbox.x_max + 1, chunk_size):
            yield ColumnRect(
                x_min=x0,
                x_max=min(x0 + chunk_size - 1, fine_bbox.x_max),
                y_min=y0,
                y_max=min(y0 + chunk_size - 1, fine_bbox.y_max),
            )


def expand_coarse_hydro_to_tile(
    coarse_by_cell: dict[tuple[int, int], object],
    tile_gx: int,
    tile_gy: int,
    map_cell: int,
) -> dict[tuple[int, int], object]:
    """Copy coarse (Gx,Gy) hydrology to every fine cell in tile."""
    entry = coarse_by_cell.get((tile_gx, tile_gy))
    if entry is None:
        return {}
    x0 = tile_origin_x(tile_gx, map_cell)
    y0 = tile_origin_y(tile_gy, map_cell)
    out: dict[tuple[int, int], object] = {}
    for ly in range(map_cell):
        for lx in range(map_cell):
            out[(x0 + lx, y0 + ly)] = entry
    return out


def is_macro_grid_coord(x: int, y: int, map_cell: int) -> bool:
    """Legacy occupancy: small indices stored as macro tile (pre-fine migration)."""
    if abs(x) >= map_cell or abs(y) >= map_cell:
        return False
    if abs(x) > 512 or abs(y) > 512:
        return False
    return True
