"""Shared light-grid hydro raster helpers (tz_map_light_bake)."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.geom.polylineRasterize import (
    bresenham_line,
)
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_to_macro_local,
    meters_to_light,
)
from app.dataModel.worldPack.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole


def dilate(cells: set[tuple[int, int]], radius: int) -> set[tuple[int, int]]:
    if radius <= 0:
        return set(cells)
    out = set(cells)
    for lx, ly in cells:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if abs(dx) + abs(dy) <= radius:
                    out.add((lx + dx, ly + dy))
    return out


def paint_role(
    compose: LightGridCompose,
    light_cells: set[tuple[int, int]],
    role: WorldMapHydrologyRole,
    *,
    width: int | None = None,
    tile_set: set[tuple[int, int]],
    preserve: frozenset[WorldMapHydrologyRole] | None = None,
) -> tuple[int, int]:
    """Merge ``role`` onto light cells; skip cells whose current role is in ``preserve``.

    Returns ``(painted, preserved_skipped)``.
    """
    scale = compose.scale
    clamped_width = HydrologyMaskWire(role=role, width=width).width
    painted = 0
    preserved = 0
    for lx, ly in light_cells:
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        if not (0 <= tx < scale.side and 0 <= ty < scale.side):
            continue
        cell = compose.ensure(gx, gy, tx, ty)
        if preserve and cell.hydrology_role in preserve:
            preserved += 1
            continue
        merged = WorldMapHydrologyRole.merge(cell.hydrology_role, role)
        cell.hydrology_role = merged
        painted += 1
        if clamped_width is not None and role is WorldMapHydrologyRole.RIVER:
            prev = cell.hydrology_width
            cell.hydrology_width = (
                clamped_width if prev is None else max(prev, clamped_width)
            )
    return painted, preserved


def meter_segments_to_light(
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    scale: LightGridScale,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    out: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for (x0, y0), (x1, y1) in segments:
        a = meters_to_light(x0, y0, scale)
        b = meters_to_light(x1, y1, scale)
        out.append((a, b))
    return out


def light_polyline_from_meters(
    points: list[tuple[int, int]],
    scale: LightGridScale,
) -> list[tuple[int, int]]:
    if len(points) < 2:
        return []
    light_pts = [meters_to_light(x, y, scale) for x, y in points]
    cells: list[tuple[int, int]] = []
    for a, b in zip(light_pts, light_pts[1:]):
        leg = bresenham_line(a[0], a[1], b[0], b[1])
        if not leg:
            continue
        if cells and cells[-1] == leg[0]:
            cells.extend(leg[1:])
        else:
            cells.extend(leg)
    return cells
