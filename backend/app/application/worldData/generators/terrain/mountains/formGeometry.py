"""FormGeometry — meters polygon + side sectors (tz_map_light_bake § Mountain)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.dataModel.terrainMasks.mountain.specs import (
    MountainFormBySides,
    PeakForm,
    PlateauForm,
    StarForm,
    form_side_count,
)


@dataclass(frozen=True, slots=True)
class SideSector:
    index: int
    edge: tuple[tuple[float, float], tuple[float, float]]
    wedge_poly: tuple[tuple[float, float], ...]
    outward_n: tuple[float, float]


@dataclass(frozen=True, slots=True)
class MountainFormGeometry:
    origin_m: tuple[float, float]
    radius_m: float
    vertices_m: tuple[tuple[float, float], ...]
    sectors: tuple[SideSector, ...]
    hat_radius_m: float | None = None


def _regular_ngon(
    origin: tuple[float, float],
    radius: float,
    n: int,
    *,
    phase: float = -math.pi / 2,
) -> list[tuple[float, float]]:
    ox, oy = origin
    verts: list[tuple[float, float]] = []
    for i in range(n):
        a = phase + 2.0 * math.pi * i / n
        verts.append((ox + radius * math.cos(a), oy + radius * math.sin(a)))
    return verts


def _star_verts(
    origin: tuple[float, float],
    radius: float,
    rays: int,
    inner_ratio: float,
    *,
    phase: float = -math.pi / 2,
) -> list[tuple[float, float]]:
    ox, oy = origin
    r_in = radius * float(inner_ratio)
    verts: list[tuple[float, float]] = []
    for i in range(rays * 2):
        a = phase + math.pi * i / rays
        r = radius if i % 2 == 0 else r_in
        verts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return verts


def _edge_outward_n(
    origin: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> tuple[float, float]:
    ex, ey = b[0] - a[0], b[1] - a[1]
    # left normal of edge direction
    nx, ny = -ey, ex
    length = math.hypot(nx, ny) or 1.0
    nx, ny = nx / length, ny / length
    mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
    to_mid = (mx - origin[0], my - origin[1])
    if nx * to_mid[0] + ny * to_mid[1] < 0:
        nx, ny = -nx, -ny
    return nx, ny


def _sectors_from_vertices(
    origin: tuple[float, float],
    vertices: list[tuple[float, float]],
    *,
    side_count: int,
) -> tuple[SideSector, ...]:
    """Map N logical sides onto vertex ring (star: every other outer edge pair)."""
    n_vert = len(vertices)
    if n_vert < 3:
        raise ValueError("form needs >= 3 vertices")
    # For star, sides == rays; each side owns wedge from origin through one outer tip edge pair.
    step = max(1, n_vert // side_count)
    sectors: list[SideSector] = []
    for i in range(side_count):
        i0 = (i * step) % n_vert
        i1 = (i0 + step) % n_vert
        a, b = vertices[i0], vertices[i1]
        outward = _edge_outward_n(origin, a, b)
        wedge = (origin, a, b)
        sectors.append(SideSector(index=i, edge=(a, b), wedge_poly=wedge, outward_n=outward))
    return tuple(sectors)


def construct_mountain_form(
    form: MountainFormBySides | StarForm | PeakForm | PlateauForm,
    origin_m: tuple[int, int] | tuple[float, float],
    radius_m: int | float,
) -> MountainFormGeometry:
    origin = (float(origin_m[0]), float(origin_m[1]))
    radius = float(radius_m)
    hat: float | None = None
    if isinstance(form, StarForm):
        verts = _star_verts(origin, radius, int(form.rays), float(form.inner_ratio))
        side_n = int(form.rays)
    elif isinstance(form, PlateauForm):
        verts = _regular_ngon(origin, radius, int(form.side_count))
        side_n = int(form.side_count)
        hat = radius * float(form.hat_fraction)
    else:
        # BySides + PeakForm — regular N-gon
        side_n = form_side_count(form)
        verts = _regular_ngon(origin, radius, side_n)
    sectors = _sectors_from_vertices(origin, verts, side_count=side_n)
    return MountainFormGeometry(
        origin_m=origin,
        radius_m=radius,
        vertices_m=tuple(verts),
        sectors=sectors,
        hat_radius_m=hat,
    )
