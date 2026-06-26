"""Perimeter ring + gate placement for outdoor barriers (settlement / area)."""

from __future__ import annotations

from app.application.worldData.generators.utils.facing import Facing


def bbox_from_cells(cells: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return min(xs), min(ys), max(xs), max(ys)


def expand_bbox(
    x0: int, y0: int, x1: int, y1: int, margin: int,
) -> tuple[int, int, int, int]:
    m = max(0, margin)
    return x0 - m, y0 - m, x1 + m, y1 + m


def perimeter_ring_bbox(
    x0:   int,
    y0:   int,
    x1:   int,
    y1:   int,
    step: int = 1,
) -> list[tuple[int, int]]:
    """Точки периметра axis-aligned bbox [x0..x1]×[y0..y1], шаг step."""
    step = max(1, step)
    points: list[tuple[int, int]] = []

    for x in range(x0, x1 + 1, step):
        points.append((x, y0))
        if y1 != y0:
            points.append((x, y1))
    for y in range(y0 + step, y1, step):
        points.append((x0, y))
        if x1 != x0:
            points.append((x1, y))

    for corner in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if corner not in points:
            points.append(corner)

    return points


def gate_on_facing_edge(
    x0:     int,
    y0:     int,
    x1:     int,
    y1:     int,
    facing: Facing,
) -> tuple[int, int]:
    """Один gate на центре грани bbox, обращённой к facing (сторона улицы)."""
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    if facing == Facing.SOUTH:
        return cx, y0
    if facing == Facing.NORTH:
        return cx, y1
    if facing == Facing.WEST:
        return x0, cy
    if facing == Facing.EAST:
        return x1, cy
    return cx, y0
