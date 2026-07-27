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


# Matches ``f"{y:4d} |"`` gutter used by ``draw_symbol_grid`` / ``draw_int_grid``.
_ROW_GUTTER = 6


def format_x_axis_ruler(x0: int, x1: int, *, gutter: int = _ROW_GUTTER) -> list[str]:
    """X ticks aligned 1:1 with 1-char cells (tens labels + ones digits)."""
    if x1 < x0:
        return []
    width = x1 - x0 + 1
    tens = [" "] * width
    ones: list[str] = []
    for i, x in enumerate(range(x0, x1 + 1)):
        ones.append(str(x % 10))
        if x % 10 != 0 and x != x0:
            continue
        label = str(x)
        start = i - len(label) + 1
        for j, ch in enumerate(label):
            pos = start + j
            if 0 <= pos < width:
                tens[pos] = ch
    pad = " " * gutter
    return [f"{pad}{''.join(tens)}", f"{pad}{''.join(ones)}"]
