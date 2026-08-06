"""Expand road_shoulder ring by graded width (RELIEF-T-16 / R22)."""

from __future__ import annotations


def expand_shoulder_ring(
    seed_cells: set[tuple[int, int]] | tuple[tuple[int, int], ...] | list[tuple[int, int]],
    ref_cells: set[tuple[int, int]],
    width: int,
) -> set[tuple[int, int]]:
    """Grow shoulder from ortho seeds away from road up to ``width`` light cells.

    ``width`` is clamped to >= 1. Seeds are ring-1 (adjacent to road). Each
    extra unit steps one cell along the unique outward ortho direction
    (from nearest road toward the seed). If nearest roads disagree on
    direction (pocket between roads), the seed is not expanded.
    Never enters ``ref_cells``.
    """
    w = max(1, int(width))
    out: set[tuple[int, int]] = set(seed_cells)
    if w == 1 or not ref_cells:
        return out
    for seed in seed_cells:
        direction = unique_outward(seed, ref_cells)
        if direction is None:
            continue
        dx, dy = direction
        x, y = seed
        for _ in range(w - 1):
            x += dx
            y += dy
            cell = (x, y)
            if cell in ref_cells:
                break
            out.add(cell)
    return out


def unique_outward(
    cell: tuple[int, int],
    ref_cells: set[tuple[int, int]],
) -> tuple[int, int] | None:
    cx, cy = cell
    best = min(abs(cx - rx) + abs(cy - ry) for rx, ry in ref_cells)
    dirs: set[tuple[int, int]] = set()
    for rx, ry in ref_cells:
        if abs(cx - rx) + abs(cy - ry) != best:
            continue
        ox, oy = cx - rx, cy - ry
        if ox != 0 and oy != 0:
            continue
        if ox != 0:
            dirs.add((1 if ox > 0 else -1, 0))
        if oy != 0:
            dirs.add((0, 1 if oy > 0 else -1))
    if len(dirs) == 1:
        return next(iter(dirs))
    return None


def relief_dz(ref_z: int, adjacent_z: int) -> int:
    """Δz road/ref minus adjacent (RELIEF-T-27) — positive → slope_down toward adjacent."""
    return int(ref_z) - int(adjacent_z)
