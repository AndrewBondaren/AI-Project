"""Settlement contributor — location_pin mask on light grid (tz_map_light_bake)."""

from __future__ import annotations

import logging

from app.application.jsonValidation.worldRow import city_sizes
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import meters_to_macro_local
from app.dataModel.worldPack.lightSettlementFootprint import LightSettlementFootprintPolicy

logger = logging.getLogger(__name__)


class SettlementContributor:
    name = "settlement"

    def __init__(self, footprint: LightSettlementFootprintPolicy | None = None) -> None:
        self._footprint = footprint or LightSettlementFootprintPolicy.canonical_defaults()

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        scale = compose.scale
        tile_set = set(ctx.tiles)
        registry = city_sizes(ctx.world)
        loc_by_uid = {loc.location_uid: loc for loc in ctx.locations}
        pins = ctx.locations_index.locations
        pins_in_tiles = 0
        cells_stamped = 0
        radii: list[int] = []

        for index, pin in enumerate(pins):
            gx, gy, tx, ty = meters_to_macro_local(pin.map_x, pin.map_y, scale)
            if (gx, gy) not in tile_set:
                continue
            pins_in_tiles += 1

            loc = loc_by_uid.get(pin.location_uid)
            size_key = loc.system_city_size if loc is not None else None
            entry = registry.entry_for(size_key) if size_key else None
            count = entry.map_cells_count if entry is not None else None
            radius = self._footprint.radius_light(count, scale.side)
            radii.append(radius)

            for dty in range(-radius, radius + 1):
                for dtx in range(-radius, radius + 1):
                    if dtx * dtx + dty * dty > radius * radius:
                        continue
                    ntx, nty = tx + dtx, ty + dty
                    ngx, ngy = gx, gy
                    if ntx < 0 or ntx >= scale.side or nty < 0 or nty >= scale.side:
                        lx = gx * scale.side + ntx
                        ly = gy * scale.side + nty
                        ngx, ngy = lx // scale.side, ly // scale.side
                        ntx, nty = lx % scale.side, ly % scale.side
                    if (ngx, ngy) not in tile_set:
                        continue
                    cell = compose.ensure(ngx, ngy, ntx, nty)
                    if cell.location_pin is None or index < cell.location_pin:
                        cell.location_pin = index
                        cells_stamped += 1

        logger.debug(
            "light_contributor_settlement | world=%s pins_total=%d pins_in_tiles=%d "
            "cells_stamped=%d radii=%s",
            ctx.world.world_uid,
            len(pins),
            pins_in_tiles,
            cells_stamped,
            radii,
        )
