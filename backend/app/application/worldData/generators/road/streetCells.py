"""Rasterize district street bed into xy cells (RAM only — C10 / C21)."""

from __future__ import annotations

from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode


def _line_cells(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    if x0 == x1:
        lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
        return [(x0, y) for y in range(lo, hi + 1)]
    if y0 == y1:
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        return [(x, y0) for x in range(lo, hi + 1)]
    cells: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        cells.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return cells


def _thicken(
    cells: list[tuple[int, int]],
    width: int,
    horizontal: bool,
) -> set[tuple[int, int]]:
    w = max(1, int(width))
    start = -((w - 1) // 2)
    end = start + w
    out: set[tuple[int, int]] = set()
    for x, y in cells:
        for off in range(start, end):
            if horizontal:
                out.add((x, y + off))
            else:
                out.add((x + off, y))
    return out


def rasterize_edge_xy(
    edge: ConnectionEdge,
    by_uid: dict[str, ConnectionNode],
) -> set[tuple[int, int]]:
    a = by_uid.get(edge.from_node_uid)
    b = by_uid.get(edge.to_node_uid)
    if a is None or b is None:
        return set()
    line = _line_cells(a.x, a.y, b.x, b.y)
    width = edge.width_cells if edge.width_cells is not None else 1
    horizontal = a.y == b.y
    return _thicken(line, width, horizontal)


def rasterize_edges_xy(
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> dict[str, set[tuple[int, int]]]:
    by_uid = {n.node_uid: n for n in nodes}
    return {edge.edge_uid: rasterize_edge_xy(edge, by_uid) for edge in edges}


def rasterize_street_xy(
    nodes: list[ConnectionNode],
    edges: list[ConnectionEdge],
) -> set[tuple[int, int]]:
    """Cells along each edge × width_cells; plus sidewalk child edges if present."""
    xy: set[tuple[int, int]] = set()
    for cells in rasterize_edges_xy(nodes, edges).values():
        xy |= cells
    return xy
