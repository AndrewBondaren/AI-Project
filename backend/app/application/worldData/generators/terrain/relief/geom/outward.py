"""Ortho outward from seed to nearest refs — shared by shoulder, clearance, C28."""

from __future__ import annotations


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


def has_relief_dz(dz: int) -> bool:
    """True when measured Δz is a grade site (RELIEF-T-27 / T-10)."""
    return int(dz) != 0


def relief_dz(ref_z: int, adjacent_z: int) -> int:
    """Δz road/ref minus adjacent (RELIEF-T-27) — positive → slope_down toward adjacent."""
    return int(ref_z) - int(adjacent_z)
