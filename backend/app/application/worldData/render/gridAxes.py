"""WORLD_SURFACE_GRID axis labels — gx/gy indices; meters as post-hoc annotation."""

from __future__ import annotations

from app.db.models.mapCell import MapCell


def is_macro_grid_coord(x: int, y: int, cell_m: int) -> bool:
    """Legacy occupancy: x/y stored as macro tile index."""
    if abs(x) >= cell_m or abs(y) >= cell_m:
        return False
    if abs(x) > 512 or abs(y) > 512:
        return False
    return True


def is_terrain_skeleton_cell(cell: MapCell, cell_m: int) -> bool:
    """Fine meter terrain column — not building shell or legacy macro occupancy."""
    if cell.system_building_element:
        return False
    if is_macro_grid_coord(cell.x, cell.y, cell_m):
        return False
    return True


# Back-compat alias (coarse-only callers)
def is_surface_grid_cell(cell: MapCell) -> bool:
    if cell.system_building_element:
        return False
    if abs(cell.x) > 512 or abs(cell.y) > 512:
        return True
    return False


def format_grid_header(
    gx0: int,
    gx1: int,
    gy0: int,
    gy1: int,
    *,
    cell_size_m: int | None = None,
    prefix: str = "",
) -> str:
    lines: list[str] = []
    head = f"{prefix}grid gx: {gx0}..{gx1}  gy: {gy0}..{gy1}"
    lines.append(head)
    if cell_size_m:
        mx0, mx1 = gx0 * cell_size_m, (gx1 + 1) * cell_size_m
        my0, my1 = gy0 * cell_size_m, (gy1 + 1) * cell_size_m
        lines.append(
            f"{prefix}meters x: {mx0}..{mx1}  y: {my0}..{my1}  (cell_size_m={cell_size_m})",
        )
    return "\n".join(lines)
