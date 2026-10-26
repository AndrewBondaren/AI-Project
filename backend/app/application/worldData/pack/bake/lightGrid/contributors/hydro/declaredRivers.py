"""Declared river corridors on the light grid (edges + intents)."""

from __future__ import annotations

from app.dataModel.hydrology.planning.hydrologyPlan import DeclaredWaterPaint
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import (
    dilate,
    light_polyline_from_fine,
    paint_role,
)
from app.dataModel.worldPack.wire.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole


def apply_declared_rivers(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    declared: DeclaredWaterPaint,
) -> dict[str, int]:
    scale = compose.scale
    tile_set = set(ctx.tiles)
    painted = 0
    edges_used = 0
    intents_used = 0

    for edge in declared.segments:
        (x0, y0), (x1, y1) = edge.segment
        light_cells = set(light_polyline_from_fine([(x0, y0), (x1, y1)], scale))
        radius = max(0, (int(edge.width_fine) + scale.light_span - 1) // scale.light_span - 1)
        light_cells = dilate(light_cells, radius)
        width = HydrologyMaskWire(
            role=WorldMapHydrologyRole.RIVER,
            width=int(edge.width_fine),
        ).width
        n, _ = paint_role(
            compose,
            light_cells,
            WorldMapHydrologyRole.RIVER,
            width=width,
            tile_set=tile_set,
        )
        if n:
            edges_used += 1
            painted += n

    for river in declared.intents:
        light_cells = set(light_polyline_from_fine(list(river.path), scale))
        n, _ = paint_role(
            compose,
            light_cells,
            WorldMapHydrologyRole.RIVER,
            width=river.width_wire,
            tile_set=tile_set,
        )
        if n:
            intents_used += 1
            painted += n

    return {
        "edges_in": len(declared.segments),
        "edges_painted": edges_used,
        "intents_in": len(declared.intents),
        "intents_painted": intents_used,
        "cells_painted": painted,
    }
