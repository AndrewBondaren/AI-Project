"""FormRaster — polygon → light cells (tz_map_light_bake § Mountain)."""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    MountainFormGeometry,
)
from app.application.worldData.masks.footprint import LightCellRef
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_cell_center_m,
    meters_to_light,
)


def _point_in_convex(px: float, py: float, verts: tuple[tuple[float, float], ...]) -> bool:
    """Pineda edge functions — all same half-plane (CCW assumed)."""
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        if (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0) < 0:
            return False
    return True


def _winding_number(px: float, py: float, verts: tuple[tuple[float, float], ...]) -> int:
    wn = 0
    n = len(verts)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        if y0 <= py:
            if y1 > py and (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0) > 0:
                wn += 1
        elif y1 <= py and (x1 - x0) * (py - y0) - (y1 - y0) * (px - x0) < 0:
            wn -= 1
    return wn


def point_in_form(px: float, py: float, geometry: MountainFormGeometry, *, concave: bool) -> bool:
    if concave:
        return _winding_number(px, py, geometry.vertices_m) != 0
    return _point_in_convex(px, py, geometry.vertices_m)


def raster_form_footprint(
    geometry: MountainFormGeometry,
    scale: LightGridScale,
    *,
    concave: bool = False,
) -> frozenset[LightCellRef]:
    """Centers of light cells inside polygon → refs."""
    xs = [v[0] for v in geometry.vertices_m]
    ys = [v[1] for v in geometry.vertices_m]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    lx0, ly0 = meters_to_light(int(min_x), int(min_y), scale)
    lx1, ly1 = meters_to_light(int(max_x), int(max_y), scale)
    side = scale.side
    cells: set[LightCellRef] = set()
    for ly in range(ly0, ly1 + 1):
        for lx in range(lx0, lx1 + 1):
            gx, gy = lx // side, ly // side
            tx, ty = lx % side, ly % side
            cx, cy = light_cell_center_m(gx, gy, tx, ty, scale)
            if point_in_form(float(cx), float(cy), geometry, concave=concave):
                cells.add(LightCellRef(gx, gy, tx, ty))
    return frozenset(cells)
