"""One hill — pure raster. Not a mask domain, not a mountain.

SoT: ``docs/tz_world_pack_storage.md`` § L2 open-land hills.
Does not read world JSON, frequency, or ``system_terrain``.
"""

from __future__ import annotations

from collections.abc import Set
from math import isqrt

from app.dataModel.terrainMasks.hillShape import HillShape

Coord = tuple[int, int]


def raster_hill(
    origin: Coord,
    *,
    radius: int,
    height: int,
    host_cells: Set[Coord],
    shape: HillShape = HillShape.CIRCLE,
    axis: int = 0,
) -> dict[Coord, int] | None:
    """Concentric rings, ``Δz`` step 1. Whole footprint ⊆ host or reject.

    ``radius`` / ``height`` / ``shape`` are already-resolved knobs.
    ``axis`` 0 = X-major, 1 = Y-major (oval / double). Not a wire field.
    """
    r = int(radius)
    h = int(height)
    if r < 1 or h < 1:
        return None
    kind = shape if isinstance(shape, HillShape) else HillShape.CIRCLE
    ax = 0 if int(axis) % 2 == 0 else 1
    if kind is not HillShape.CIRCLE and r < 2:
        kind = HillShape.CIRCLE
    delta: dict[Coord, int] = {}
    if kind is HillShape.CIRCLE:
        _add_disk(delta, origin, r, h)
    elif kind is HillShape.OVAL:
        _add_oval(delta, origin, r, h, ax)
    else:
        s = max(1, r // 3)
        lobe = r - s
        if lobe < 1:
            _add_disk(delta, origin, r, h)
        else:
            c1, c2 = _pair_centers(origin, s, ax)
            if kind is HillShape.DOUBLE_CIRCLE:
                _add_disk(delta, c1, lobe, h)
                _add_disk(delta, c2, lobe, h)
            else:
                _add_oval(delta, c1, lobe, h, ax)
                _add_oval(delta, c2, lobe, h, ax)
    if not delta:
        return None
    if any(xy not in host_cells for xy in delta):
        return None
    return delta


def _terrace(dist: int, radius: int, height: int) -> int:
    return height - min(height - 1, (dist * height) // radius)


def _add_disk(delta: dict[Coord, int], origin: Coord, radius: int, height: int) -> None:
    ox, oy = origin
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            xy = (ox + dx, oy + dy)
            dz = _terrace(isqrt(d2), radius, height)
            if dz > delta.get(xy, 0):
                delta[xy] = dz


def _ellipse_d2(dx: int, dy: int, axis: int) -> int:
    if axis == 0:
        return dx * dx + 4 * dy * dy
    return 4 * dx * dx + dy * dy


def _add_oval(
    delta: dict[Coord, int], origin: Coord, radius: int, height: int, axis: int,
) -> None:
    ox, oy = origin
    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            d2 = _ellipse_d2(dx, dy, axis)
            if d2 > r2:
                continue
            xy = (ox + dx, oy + dy)
            dz = _terrace(isqrt(d2), radius, height)
            if dz > delta.get(xy, 0):
                delta[xy] = dz


def _pair_centers(origin: Coord, split: int, axis: int) -> tuple[Coord, Coord]:
    ox, oy = origin
    if axis == 0:
        return (ox + split, oy), (ox - split, oy)
    return (ox, oy + split), (ox, oy - split)
