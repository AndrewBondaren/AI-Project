"""Rasterize declare connection polylines to grid cells — D HY-2."""

from __future__ import annotations


def bresenham_line(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> list[tuple[int, int]]:
    """Integer grid line from (x0,y0) to (x1,y1) inclusive."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points


def rasterize_segments(
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
) -> set[tuple[int, int]]:
    """Union of grid cells covered by segment list."""
    cells: set[tuple[int, int]] = set()
    for (x0, y0), (x1, y1) in segments:
        for cell in bresenham_line(x0, y0, x1, y1):
            cells.add(cell)
    return cells
