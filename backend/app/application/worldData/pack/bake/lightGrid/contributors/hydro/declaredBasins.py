"""Declared lakes + coastline on the light grid."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.geom.polylineRasterize import (
    rasterize_segments,
)
from app.application.worldData.generators.hydrology.geom.polygonInterior import (
    point_in_polygon,
    polygon_vertices,
)
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    LoadedDeclaredHydrology,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import (
    meter_segments_to_light,
    paint_role,
)
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole


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


def apply_declared_basins(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    declared: LoadedDeclaredHydrology,
) -> dict[str, int]:
    scale = compose.scale
    tile_set = set(ctx.tiles)
    shore_n = 0
    lake_n = 0
    coast_n = 0

    for lake in declared.lake_specs:
        light_segs = meter_segments_to_light(lake.shoreline_segments, scale)
        shoreline = rasterize_segments(light_segs)
        interior = _lake_interior_light(light_segs, shoreline)
        sn, _ = paint_role(compose, shoreline, WorldMapHydrologyRole.SHORE, tile_set=tile_set)
        ln, _ = paint_role(compose, interior, WorldMapHydrologyRole.LAKE, tile_set=tile_set)
        shore_n += sn
        lake_n += ln

    if declared.coastline_segments:
        light_segs = meter_segments_to_light(declared.coastline_segments, scale)
        shore = rasterize_segments(light_segs)
        cn, _ = paint_role(compose, shore, WorldMapHydrologyRole.SHORE, tile_set=tile_set)
        coast_n += cn

    return {
        "lakes_in": len(declared.lake_specs),
        "shore_cells": shore_n,
        "lake_cells": lake_n,
        "coast_cells": coast_n,
        "has_coastline": 1 if declared.coastline_segments else 0,
    }
