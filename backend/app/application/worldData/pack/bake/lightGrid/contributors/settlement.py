"""Settlement contributor — location_pin mask on light grid (tz_map_light_bake)."""

from __future__ import annotations

import math

from app.application.jsonValidation.worldRow import city_sizes
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import meters_to_macro_local
from app.dataModel.settlement.settlement.citySizeEntry import CitySizeEntry


def _footprint_radius_light(entry: CitySizeEntry | None, side: int) -> int:
    """Coarse city size → light-cell disk radius (mask, not single pin)."""
    count = 1
    if entry is not None and entry.map_cells_count is not None:
        count = max(1, int(entry.map_cells_count))
    return max(1, int(math.ceil(math.sqrt(count) * (side / 8.0))))


class SettlementContributor:
    name = "settlement"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        scale = compose.scale
        tile_set = set(ctx.tiles)
        registry = city_sizes(ctx.world)
        pins = ctx.locations_index.locations

        for index, pin in enumerate(pins):
            gx, gy, tx, ty = meters_to_macro_local(pin.map_x, pin.map_y, scale)
            if (gx, gy) not in tile_set:
                continue

            loc = next(
                (l for l in ctx.locations if l.location_uid == pin.location_uid),
                None,
            )
            size_key = loc.system_city_size if loc is not None else None
            entry = registry.entry_for(size_key) if size_key else None
            radius = _footprint_radius_light(entry, scale.side)

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
