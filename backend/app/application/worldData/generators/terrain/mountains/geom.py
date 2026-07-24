"""Shared mountain geometry helpers — tz_map_light_bake Q6."""

from __future__ import annotations

import math


def dist_point_to_segment_m(
    px: float,
    py: float,
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_point_to_polyline_m(
    px: float,
    py: float,
    spine: list[tuple[int, int]] | list[tuple[float, float]],
) -> float:
    if len(spine) < 2:
        if not spine:
            return float("inf")
        return math.hypot(px - float(spine[0][0]), py - float(spine[0][1]))
    best = float("inf")
    for i in range(len(spine) - 1):
        a = (float(spine[i][0]), float(spine[i][1]))
        b = (float(spine[i + 1][0]), float(spine[i + 1][1]))
        d = dist_point_to_segment_m(px, py, a, b)
        if d < best:
            best = d
    return best
