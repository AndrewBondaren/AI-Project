"""SystemCluster — group summit anchors by peak_gap_m (tz_mountain_architecture)."""

from __future__ import annotations

import math

from app.application.worldData.generators.terrain.mountains.peakGap import peak_gap_m_for_spec
from app.application.worldData.generators.terrain.mountains.ridgeGraph.types import (
    MountainSystem,
    RidgeVertex,
)
from app.application.worldData.generators.terrain.mountains.summitAnchor import (
    summit_anchor,
    summit_hat_radius_m,
)
from app.dataModel.terrainMasks.mountain.specs import MountainSpec

__all__ = [
    "cluster_systems",
    "peak_gap_m_for_spec",
    "vertices_from_peaks",
]


def vertices_from_peaks(peaks: list[MountainSpec]) -> list[RidgeVertex]:
    out: list[RidgeVertex] = []
    for i, peak in enumerate(peaks):
        x, y = summit_anchor(peak)
        out.append(
            RidgeVertex(
                index=i,
                x_m=x,
                y_m=y,
                peak=peak,
                hat_radius_m=summit_hat_radius_m(peak),
            )
        )
    return out


def cluster_systems(vertices: list[RidgeVertex]) -> list[MountainSystem]:
    """Union-find clusters: link if dist <= max(peak_gap of either)."""
    n = len(vertices)
    if n == 0:
        return []
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    gaps = [peak_gap_m_for_spec(v.peak) for v in vertices]
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(vertices[i].x_m - vertices[j].x_m, vertices[i].y_m - vertices[j].y_m)
            if d <= max(gaps[i], gaps[j]):
                union(i, j)

    buckets: dict[int, list[RidgeVertex]] = {}
    for i, v in enumerate(vertices):
        buckets.setdefault(find(i), []).append(v)

    systems: list[MountainSystem] = []
    for group in buckets.values():
        gap = max(peak_gap_m_for_spec(v.peak) for v in group)
        systems.append(MountainSystem(vertices=tuple(group), peak_gap_m=gap))
    return systems
