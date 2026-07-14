"""WORLD_SURFACE_GRID axis labels — gx/gy indices; meters as post-hoc annotation."""

from __future__ import annotations


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
