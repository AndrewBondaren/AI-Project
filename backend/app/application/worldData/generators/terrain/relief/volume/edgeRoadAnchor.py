"""Footprint-edge road abutment for ribbon grade — tz_terrain_relief edgeRoadAnchor.

``abutment = seed - outward``; must be ∈ ``ref_cells``. Not centerline / not
global Manhattan nearest.
"""

from __future__ import annotations

from dataclasses import dataclass

Coord = tuple[int, int]


@dataclass(frozen=True, slots=True)
class EdgeRoadAnchor:
    """One seed's edge abutment on the painted road / ribbon ref footprint."""

    xy: Coord
    outward: tuple[int, int]
    z: int
    center_m: tuple[float, float]


def cell_center_m(xy: Coord) -> tuple[float, float]:
    """Meter-cell center in cell space (half-cell, not a pack/light helper)."""
    return (xy[0] + 0.5, xy[1] + 0.5)


def edge_road_abutment(
    seed: Coord,
    outward: tuple[int, int],
    ref_cells: set[Coord],
) -> Coord | None:
    """Return abutment cell, or ``None`` if not on ``ref_cells``."""
    dx, dy = int(outward[0]), int(outward[1])
    if (dx, dy) == (0, 0) or abs(dx) + abs(dy) != 1:
        return None
    ax, ay = int(seed[0]) - dx, int(seed[1]) - dy
    abutment = (ax, ay)
    if abutment not in ref_cells:
        return None
    return abutment
