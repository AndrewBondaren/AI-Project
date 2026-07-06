"""Load map_cells and produce ASCII grid renders — debug only."""

from __future__ import annotations

from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.render.locationGridRenderer import LocationGridRenderer
from app.application.worldData.render.worldGridRenderer import WorldGridRenderer
from app.db.models.namedLocation import NamedLocation


class MapGridRenderService:
    def __init__(self, map_cell_service: MapCellService) -> None:
        self._map_cells = map_cell_service

    async def render_world_grid(
        self,
        world_uid: str,
        *,
        locations: list[NamedLocation] | None = None,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
    ) -> dict[str, str]:
        cells = await self._map_cells.get_all(world_uid)
        renderer = WorldGridRenderer(cells, locations=locations)
        if gx0 is not None and gy0 is not None and gx1 is not None and gy1 is not None:
            ascii_grid = renderer.render_bbox(gx0, gy0, gx1, gy1)
        else:
            ascii_grid = renderer.render()
        return {
            "ascii": ascii_grid,
            "legend": WorldGridRenderer.render_legend(),
        }

    async def render_location_grid(
        self,
        world_uid: str,
        location_uid: str,
        *,
        z: int | None = None,
    ) -> dict[str, str | dict[int, str]]:
        cells = await self._map_cells.get_all(world_uid)
        renderer = LocationGridRenderer(cells, location_uid)
        legend = WorldGridRenderer.render_legend()
        if z is not None:
            return {"ascii": renderer.render_level(z), "legend": legend, "z": z}
        levels = renderer.render_all_levels()
        return {"levels": levels, "legend": legend}
