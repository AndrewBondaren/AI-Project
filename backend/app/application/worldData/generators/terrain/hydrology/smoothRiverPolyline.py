"""U14 river polyline turn limit (≤ 45°) — D HY-5c."""

from __future__ import annotations

import math


def turn_angle_deg(
    a: tuple[int, int],
    b: tuple[int, int],
    c: tuple[int, int],
) -> float:
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    if v1 == (0, 0) or v2 == (0, 0):
        return 0.0
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    l1 = math.hypot(v1[0], v1[1])
    l2 = math.hypot(v2[0], v2[1])
    cos_angle = max(-1.0, min(1.0, dot / (l1 * l2)))
    return math.degrees(math.acos(cos_angle))


def step_turn_ok(
    path: list[tuple[int, int]],
    candidate: tuple[int, int],
    *,
    max_turn_deg: float = 45.0,
) -> bool:
    if len(path) < 2:
        return True
    return turn_angle_deg(path[-2], path[-1], candidate) <= max_turn_deg


def smooth_polyline_cells(
    cells: list[tuple[int, int]],
    *,
    max_turn_deg: float = 45.0,
) -> list[tuple[int, int]]:
    """Drop steps that would break U14 turn limit."""
    if len(cells) <= 2:
        return list(cells)
    out = [cells[0], cells[1]]
    for cell in cells[2:]:
        if step_turn_ok(out, cell, max_turn_deg=max_turn_deg):
            out.append(cell)
    return out
