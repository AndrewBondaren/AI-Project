"""Expand road_shoulder ring by graded width (RELIEF-T-16 / R22)."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.geom.outward import unique_outward


def expand_shoulder_ring(
    seed_cells: set[tuple[int, int]] | tuple[tuple[int, int], ...] | list[tuple[int, int]],
    ref_cells: set[tuple[int, int]],
    width: int,
) -> set[tuple[int, int]]:
    """Grow shoulder from ortho seeds away from road up to ``width`` light cells.

    ``width`` is ``slope_length_cells`` / outward L (RELIEF-T-38):
    - ``<= 0`` → empty (honor explicit 0; no silent clamp to 1)
    - ``1`` → seed ring only (no extra steps)
    - ``> 1`` → seed + ``width - 1`` ortho steps outward

    Seeds are ring-1 (adjacent to road). Extra units step along the unique
    outward ortho direction (from nearest road toward the seed). If nearest
    roads disagree on direction (pocket between roads), the seed is not
    expanded. Never enters ``ref_cells``.
    """
    w = int(width)
    if w <= 0:
        return set()
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
