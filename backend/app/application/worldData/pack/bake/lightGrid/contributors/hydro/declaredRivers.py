"""Declared river corridors on the light grid (edges + intents)."""

from __future__ import annotations

from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    LoadedDeclaredHydrology,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.raster import (
    dilate,
    light_polyline_from_meters,
    paint_role,
)
from app.dataModel.worldPack.hydrologyMaskWire import HydrologyMaskWire, WorldMapHydrologyRole

# Intent corridors without explicit width — HydrologyMaskWire clamp is SoT.
_INTENT_RIVER_WIDTH = HydrologyMaskWire(
    role=WorldMapHydrologyRole.RIVER,
    width=1,
).width


def apply_declared_rivers(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    declared: LoadedDeclaredHydrology,
) -> dict[str, int]:
    scale = compose.scale
    tile_set = set(ctx.tiles)
    painted = 0
    edges_used = 0
    intents_used = 0

    for edge in declared.river_edges:
        (x0, y0), (x1, y1) = edge.segment
        light_cells = set(light_polyline_from_meters([(x0, y0), (x1, y1)], scale))
        radius = max(0, (int(edge.width_cells) + scale.light_m - 1) // scale.light_m - 1)
        light_cells = dilate(light_cells, radius)
        width = HydrologyMaskWire(
            role=WorldMapHydrologyRole.RIVER,
            width=int(edge.width_cells),
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
        light_cells = set(light_polyline_from_meters(anchors, scale))
        n, _ = paint_role(
            compose,
            light_cells,
            WorldMapHydrologyRole.RIVER,
            width=_INTENT_RIVER_WIDTH,
            tile_set=tile_set,
        )
        if n:
            intents_used += 1
            painted += n

    return {
        "edges_in": len(declared.river_edges),
        "edges_painted": edges_used,
        "intents_in": len(declared.river_intents),
        "intents_painted": intents_used,
        "cells_painted": painted,
    }
