"""Delaunay → MST ridge graph — tz_mountain_architecture."""

from __future__ import annotations

import math

from app.application.worldData.generators.terrain.mountains.ridgeGraph.types import (
    RidgeEdge,
    RidgeGraph,
    RidgeVertex,
)


def _dist(a: RidgeVertex, b: RidgeVertex) -> float:
    return math.hypot(a.x_m - b.x_m, a.y_m - b.y_m)


def _circumcircle(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float,
) -> tuple[float, float, float] | None:
    """Return (ux, uy, r²) or None if points are collinear."""
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = (
        (ax * ax + ay * ay) * (by - cy)
        + (bx * bx + by * by) * (cy - ay)
        + (cx * cx + cy * cy) * (ay - by)
    ) / d
    uy = (
        (ax * ax + ay * ay) * (cx - bx)
        + (bx * bx + by * by) * (ax - cx)
        + (cx * cx + cy * cy) * (bx - ax)
    ) / d
    r2 = (ux - ax) ** 2 + (uy - ay) ** 2
    return ux, uy, r2


def delaunay_edges(vertices: tuple[RidgeVertex, ...] | list[RidgeVertex]) -> list[RidgeEdge]:
    """Bowyer–Watson Delaunay edges for small peak sets (no scipy)."""
    pts = list(vertices)
    n = len(pts)
    if n < 2:
        return []
    if n == 2:
        return [RidgeEdge(0, 1, _dist(pts[0], pts[1]))]

    # Super-triangle bounding all points.
    xs = [p.x_m for p in pts]
    ys = [p.y_m for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = max(max_x - min_x, 1.0)
    dy = max(max_y - min_y, 1.0)
    mid_x = (min_x + max_x) / 2.0
    mid_y = (min_y + max_y) / 2.0
    st = [
        (mid_x - 20 * dx, mid_y - dy),
        (mid_x, mid_y + 20 * dy),
        (mid_x + 20 * dx, mid_y - dy),
    ]
    # Triangles as index triples into pts + 3 super verts.
    coords = [(p.x_m, p.y_m) for p in pts] + st
    triangles: list[tuple[int, int, int]] = [(n, n + 1, n + 2)]

    for i in range(n):
        bad: list[tuple[int, int, int]] = []
        for tri in triangles:
            circ = _circumcircle(
                coords[tri[0]][0], coords[tri[0]][1],
                coords[tri[1]][0], coords[tri[1]][1],
                coords[tri[2]][0], coords[tri[2]][1],
            )
            if circ is None:
                continue
            ux, uy, r2 = circ
            px, py = coords[i]
            if (px - ux) ** 2 + (py - uy) ** 2 <= r2 + 1e-9:
                bad.append(tri)
        # Polygon = boundary of bad triangles.
        edge_count: dict[tuple[int, int], int] = {}
        for a, b, c in bad:
            for u, v in ((a, b), (b, c), (c, a)):
                e = (u, v) if u < v else (v, u)
                edge_count[e] = edge_count.get(e, 0) + 1
        boundary = [e for e, c in edge_count.items() if c == 1]
        triangles = [t for t in triangles if t not in bad]
        for u, v in boundary:
            triangles.append((u, v, i))

    edge_set: set[tuple[int, int]] = set()
    for a, b, c in triangles:
        if a >= n or b >= n or c >= n:
            continue
        for u, v in ((a, b), (b, c), (c, a)):
            e = (u, v) if u < v else (v, u)
            edge_set.add(e)

    # Remap vertex indices: triangulation used local 0..n-1; RidgeVertex.index may differ.
    index_of = {i: pts[i].index for i in range(n)}
    out: list[RidgeEdge] = []
    for u, v in sorted(edge_set):
        iu, iv = index_of[u], index_of[v]
        # find vertices by local order for distance
        du = _dist(pts[u], pts[v])
        out.append(RidgeEdge(min(iu, iv), max(iu, iv), du))
    return out


def mst_from_edges(
    vertices: tuple[RidgeVertex, ...] | list[RidgeVertex],
    edges: list[RidgeEdge],
) -> list[RidgeEdge]:
    """Kruskal MST on given undirected edges."""
    if len(vertices) < 2:
        return []
    ids = sorted({v.index for v in vertices})
    parent = {i: i for i in ids}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    mst: list[RidgeEdge] = []
    for e in sorted(edges, key=lambda x: x.length_m):
        if union(e.a, e.b):
            mst.append(e)
            if len(mst) == len(ids) - 1:
                break
    return mst


def build_mst_graph(vertices: list[RidgeVertex] | tuple[RidgeVertex, ...]) -> RidgeGraph:
    verts = tuple(vertices)
    if len(verts) < 2:
        return RidgeGraph(vertices=verts, edges=())
    # Remap to contiguous local indices for Delaunay, then restore RidgeVertex.index.
    local = [
        RidgeVertex(index=i, x_m=v.x_m, y_m=v.y_m, peak=v.peak, hat_radius_m=v.hat_radius_m)
        for i, v in enumerate(verts)
    ]
    del_edges = delaunay_edges(local)
    # Map local edge indices → original vertex.index
    mapped = [
        RidgeEdge(
            a=verts[e.a].index,
            b=verts[e.b].index,
            length_m=e.length_m,
        )
        for e in del_edges
    ]
    if not mapped and len(verts) >= 2:
        # Degenerate (collinear): fall back to complete graph MST.
        mapped = []
        for i in range(len(verts)):
            for j in range(i + 1, len(verts)):
                mapped.append(
                    RidgeEdge(
                        a=verts[i].index,
                        b=verts[j].index,
                        length_m=_dist(verts[i], verts[j]),
                    )
                )
    mst = mst_from_edges(verts, mapped)
    return RidgeGraph(vertices=verts, edges=tuple(mst))
