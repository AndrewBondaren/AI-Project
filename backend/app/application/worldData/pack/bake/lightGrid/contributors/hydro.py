"""Hydro contributor — Path A light-rasterize (tz_map_light_bake)."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.geom.polylineRasterize import (
    bresenham_line,
    rasterize_segments,
)
from app.application.worldData.generators.hydrology.geom.polygonInterior import (
    point_in_polygon,
    polygon_vertices,
)
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_to_macro_local,
    meters_to_light,
)
from app.application.worldData.pack.bake.worldMapHydrology import world_map_hydro_role_from_cell
from app.dataModel.worldPack.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole


def _dilate(cells: set[tuple[int, int]], radius: int) -> set[tuple[int, int]]:
    if radius <= 0:
        return set(cells)
    out = set(cells)
    for lx, ly in cells:
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if abs(dx) + abs(dy) <= radius:
                    out.add((lx + dx, ly + dy))
    return out


def _paint_role(
    compose: LightGridCompose,
    light_cells: set[tuple[int, int]],
    role: WorldMapHydrologyRole,
    *,
    width: int | None = None,
    tile_set: set[tuple[int, int]],
) -> None:
    scale = compose.scale
    clamped_width = HydrologyMaskWire(role=role, width=width).width
    for lx, ly in light_cells:
        gx, gy, tx, ty = light_to_macro_local(lx, ly, scale)
        if (gx, gy) not in tile_set:
            continue
        if not (0 <= tx < scale.side and 0 <= ty < scale.side):
            continue
        cell = compose.ensure(gx, gy, tx, ty)
        merged = WorldMapHydrologyRole.merge(cell.hydrology_role, role)
        cell.hydrology_role = merged
        if clamped_width is not None and role is WorldMapHydrologyRole.RIVER:
            prev = cell.hydrology_width
            cell.hydrology_width = (
                clamped_width if prev is None else max(prev, clamped_width)
            )


def _meter_segments_to_light(
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    scale: LightGridScale,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    out: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for (x0, y0), (x1, y1) in segments:
        a = meters_to_light(x0, y0, scale)
        b = meters_to_light(x1, y1, scale)
        out.append((a, b))
    return out


def _light_polyline_from_meters(
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


def _lake_interior_light(
    light_segments: list[tuple[tuple[int, int], tuple[int, int]]],
    shoreline: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    verts = polygon_vertices(light_segments)
    if len(verts) < 3:
        return set()
    xs = [int(v[0]) for v in verts]
    ys = [int(v[1]) for v in verts]
    interior: set[tuple[int, int]] = set()
    for ly in range(min(ys) - 1, max(ys) + 2):
        for lx in range(min(xs) - 1, max(xs) + 2):
            key = (lx, ly)
            if key in shoreline:
                continue
            if point_in_polygon(lx + 0.5, ly + 0.5, verts):
                interior.add(key)
    return interior


class HydroContributor:
    name = "hydro"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        if not is_hydrology_enabled(ctx.world):
            return

        scale = compose.scale
        tile_set = set(ctx.tiles)
        declared = load_declared_hydrology(ctx.world, ctx.locations)

        for edge in declared.river_edges:
            (x0, y0), (x1, y1) = edge.segment
            light_cells = set(_light_polyline_from_meters([(x0, y0), (x1, y1)], scale))
            radius = max(0, (int(edge.width_cells) + scale.light_m - 1) // scale.light_m - 1)
            light_cells = _dilate(light_cells, radius)
            width = HydrologyMaskWire(
                role=WorldMapHydrologyRole.RIVER,
                width=min(15, max(1, int(edge.width_cells))),
            ).width
            _paint_role(
                compose,
                light_cells,
                WorldMapHydrologyRole.RIVER,
                width=width,
                tile_set=tile_set,
            )

        loc_map = {loc.location_uid: loc for loc in ctx.locations}

        def _anchor_xy(uid: str | None) -> tuple[int, int] | None:
            if not uid:
                return None
            loc = loc_map.get(uid)
            if loc is None or loc.map_x is None or loc.map_y is None:
                return None
            return int(loc.map_x), int(loc.map_y)

        for river in declared.river_intents:
            anchors: list[tuple[int, int]] = []
            if river.source is not None and river.source.x is not None and river.source.y is not None:
                anchors.append((int(river.source.x), int(river.source.y)))
            for uid in river.route_location_uids:
                pt = _anchor_xy(uid)
                if pt is not None:
                    anchors.append(pt)
            if river.mouth is not None:
                if river.mouth.x is not None and river.mouth.y is not None:
                    anchors.append((int(river.mouth.x), int(river.mouth.y)))
                else:
                    pt = _anchor_xy(river.mouth.location_uid)
                    if pt is not None:
                        anchors.append(pt)
            if len(anchors) < 2:
                continue
            light_cells = set(_light_polyline_from_meters(anchors, scale))
            _paint_role(
                compose,
                light_cells,
                WorldMapHydrologyRole.RIVER,
                width=1,
                tile_set=tile_set,
            )

        for lake in declared.lake_specs:
            light_segs = _meter_segments_to_light(lake.shoreline_segments, scale)
            shoreline = rasterize_segments(light_segs)
            interior = _lake_interior_light(light_segs, shoreline)
            _paint_role(compose, shoreline, WorldMapHydrologyRole.SHORE, tile_set=tile_set)
            _paint_role(compose, interior, WorldMapHydrologyRole.LAKE, tile_set=tile_set)

        if declared.coastline_segments:
            light_segs = _meter_segments_to_light(declared.coastline_segments, scale)
            shore = rasterize_segments(light_segs)
            _paint_role(compose, shore, WorldMapHydrologyRole.SHORE, tile_set=tile_set)

        # Areal SEA/LAKE from coarse planning only — not coarse RIVER stamp.
        planning = ctx.surface_planning
        if planning is None:
            return
        for gx, gy in ctx.tiles:
            role = world_map_hydro_role_from_cell(planning.coarse_hydro.get((gx, gy)))
            if role not in (WorldMapHydrologyRole.SEA, WorldMapHydrologyRole.LAKE):
                continue
            fill = {
                (gx * scale.side + tx, gy * scale.side + ty)
                for ty in range(scale.side)
                for tx in range(scale.side)
            }
            _paint_role(compose, fill, role, tile_set=tile_set)
