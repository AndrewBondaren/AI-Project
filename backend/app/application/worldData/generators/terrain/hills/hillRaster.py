"""One hill — pure raster. Not a mask domain, not a mountain.

SoT: ``docs/tz_world_pack_storage.md`` § L2 open-land hills.
Does not read world JSON, frequency, or ``system_terrain``.
"""

from __future__ import annotations

from collections.abc import Set
from math import isqrt

from app.dataModel.terrainMasks.hillShape import HillShape
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.hills.acceptedHill import AcceptedHill

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
    delta = _geometry(origin, radius, height, shape, axis)
    if delta is None or any(xy not in host_cells for xy in delta):
        return None
    return delta


def raster_hill_window(hill: AcceptedHill, bounds: GridBBox) -> dict[Coord, int]:
    """Rasterize already admitted geometry; never re-check hosts or select origins."""
    return _geometry(hill.origin, hill.radius, hill.height, hill.shape, hill.axis, bounds) or {}


def _geometry(origin: Coord, radius: int, height: int, shape: HillShape, axis: int,
              clip: GridBBox | None = None) -> dict[Coord, int] | None:
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
        _add_disk(delta, origin, r, h, clip)
    elif kind is HillShape.OVAL:
        _add_oval(delta, origin, r, h, ax, clip)
    else:
        s = max(1, r // 3)
        lobe = r - s
        if lobe < 1:
            _add_disk(delta, origin, r, h, clip)
        else:
            c1, c2 = _pair_centers(origin, s, ax)
            if kind is HillShape.DOUBLE_CIRCLE:
                _add_disk(delta, c1, lobe, h, clip)
                _add_disk(delta, c2, lobe, h, clip)
            else:
                _add_oval(delta, c1, lobe, h, ax, clip)
                _add_oval(delta, c2, lobe, h, ax, clip)
    if not delta:
        return None
    return delta


def _terrace(dist: int, radius: int, height: int) -> int:
    return height - min(height - 1, (dist * height) // radius)


def _add_disk(delta: dict[Coord, int], origin: Coord, radius: int, height: int,
              clip: GridBBox | None = None) -> None:
    ox, oy = origin
    r2 = radius * radius
    x0, x1 = (-radius, radius) if clip is None else (max(-radius, clip.x_min-ox), min(radius, clip.x_max-ox))
    y0, y1 = (-radius, radius) if clip is None else (max(-radius, clip.y_min-oy), min(radius, clip.y_max-oy))
    for dy in range(y0, y1 + 1):
        for dx in range(x0, x1 + 1):
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
    clip: GridBBox | None = None,
) -> None:
    ox, oy = origin
    r2 = radius * radius
    x0, x1 = (-radius, radius) if clip is None else (max(-radius, clip.x_min-ox), min(radius, clip.x_max-ox))
    y0, y1 = (-radius, radius) if clip is None else (max(-radius, clip.y_min-oy), min(radius, clip.y_max-oy))
    for dy in range(y0, y1 + 1):
        for dx in range(x0, x1 + 1):
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
