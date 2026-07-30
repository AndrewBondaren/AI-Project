"""SpineSampler — MST + MountainRangeStyle → polyline (tz_mountain_architecture)."""

from __future__ import annotations

import math
from collections import defaultdict

from app.application.worldData.generators.terrain.mountains.ridgeGraph.types import (
    RidgeEdge,
    RidgeGraph,
    RidgeVertex,
)
from app.dataModel.terrainMasks.mountain.enums import MountainRangeStyle


def _by_index(graph: RidgeGraph) -> dict[int, RidgeVertex]:
    return {v.index: v for v in graph.vertices}


def _path_order(graph: RidgeGraph) -> list[int]:
    """Order MST vertices along a diameter path (tree → path approx)."""
    if not graph.vertices:
        return []
    if len(graph.vertices) == 1:
        return [graph.vertices[0].index]
    adj: dict[int, list[int]] = defaultdict(list)
    for e in graph.edges:
        adj[e.a].append(e.b)
        adj[e.b].append(e.a)

    def farthest(start: int) -> tuple[int, list[int]]:
        prev: dict[int, int | None] = {start: None}
        stack = [start]
        last = start
        while stack:
            u = stack.pop()
            last = u
            for v in adj[u]:
                if v not in prev:
                    prev[v] = u
                    stack.append(v)
        path = [last]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])  # type: ignore[arg-type]
        path.reverse()
        return last, path

    leaves = [v.index for v in graph.vertices if len(adj[v.index]) <= 1]
    start = leaves[0] if leaves else graph.vertices[0].index
    end, _ = farthest(start)
    _, path = farthest(end)
    return path


def _lerp(a: RidgeVertex, b: RidgeVertex, t: float) -> tuple[int, int]:
    x = a.x_m + (b.x_m - a.x_m) * t
    y = a.y_m + (b.y_m - a.y_m) * t
    return int(round(x)), int(round(y))


def _edge_for(a: int, b: int, edges: tuple[RidgeEdge, ...]) -> RidgeEdge | None:
    lo, hi = (a, b) if a < b else (b, a)
    for e in edges:
        ea, eb = (e.a, e.b) if e.a < e.b else (e.b, e.a)
        if ea == lo and eb == hi:
            return e
    return None


def sample_spine(
    graph: RidgeGraph,
    style: MountainRangeStyle,
    *,
    peak_gap_m: float,
    hybrid_smooth_edge_factor: float = 1.5,
) -> list[tuple[int, int]]:
    """Sample MST into MountainRangeSpec.spine polyline."""
    order = _path_order(graph)
    by_i = _by_index(graph)
    if len(order) < 2:
        if order:
            v = by_i[order[0]]
            return [(int(round(v.x_m)), int(round(v.y_m)))]
        return []

    smooth_min_m = float(peak_gap_m) * float(hybrid_smooth_edge_factor)
    pts: list[tuple[int, int]] = []

    def push(p: tuple[int, int]) -> None:
        if not pts or pts[-1] != p:
            pts.append(p)

    for i in range(len(order) - 1):
        a_i, b_i = order[i], order[i + 1]
        a, b = by_i[a_i], by_i[b_i]
        push((int(round(a.x_m)), int(round(a.y_m))))
        edge = _edge_for(a_i, b_i, graph.edges)
        length = edge.length_m if edge is not None else math.hypot(a.x_m - b.x_m, a.y_m - b.y_m)
        use_smooth = style == MountainRangeStyle.SMOOTH
        if style == MountainRangeStyle.HYBRID:
            use_smooth = length >= smooth_min_m
        if use_smooth and length > 1.0:
            # densify step = peak_gap/2 — algorithmic (not POJO); U7 densify knob later
            steps = max(1, int(length / max(1.0, peak_gap_m * 0.5)))
            for s in range(1, steps):
                push(_lerp(a, b, s / steps))
        # broken: endpoints only (already pushed a; b on next iter / final)
    last = by_i[order[-1]]
    push((int(round(last.x_m)), int(round(last.y_m))))
    if len(pts) < 2:
        # Ensure min_length=2 for MountainRangeSpec
        push((pts[0][0] + 1, pts[0][1]))
    return pts
