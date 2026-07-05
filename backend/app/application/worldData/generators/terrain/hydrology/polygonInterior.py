"""Grid polygon interior fill — D HY-3."""

from __future__ import annotations

from app.application.worldData.generators.terrain.types import SurfaceHeightmap


def polygon_vertices(
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[float, float]]:
    seen: set[tuple[int, int]] = set()
    verts: list[tuple[float, float]] = []
    for a, b in segments:
        for p in (a, b):
            if p not in seen:
                seen.add(p)
                verts.append((float(p[0]), float(p[1])))
    return verts


def point_in_polygon(x: float, y: float, vertices: list[tuple[float, float]]) -> bool:
    """Ray-cast test for simple polygon."""
    if len(vertices) < 3:
        return False
    inside = False
    n = len(vertices)
    for i in range(n):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        if ((y0 > y) != (y1 > y)) and (
            x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0
        ):
            inside = not inside
    return inside


def interior_cells(
    heightmap: SurfaceHeightmap,
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    shoreline: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    verts = polygon_vertices(segments)
    if len(verts) < 3:
        return set()
    xs = [int(v[0]) for v in verts]
    ys = [int(v[1]) for v in verts]
    interior: set[tuple[int, int]] = set()
    for gy in range(min(ys) - 1, max(ys) + 2):
        for gx in range(min(xs) - 1, max(xs) + 2):
            key = (gx, gy)
            if key not in heightmap.surface_z or key in shoreline:
                continue
            if point_in_polygon(gx + 0.5, gy + 0.5, verts):
                interior.add(key)
    return interior
