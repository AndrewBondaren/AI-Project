"""Load map_cells and produce ASCII grid renders — debug only."""

from __future__ import annotations

from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.render.locationGridRenderer import LocationGridRenderer
from app.application.worldData.render.worldGridRenderer import WorldGridRenderer
from app.application.worldData.render.worldTileGridRenderer import WorldTileGridRenderer
from app.application.worldData.worldService import WorldService
from app.db.models.namedLocation import NamedLocation


class MapGridRenderService:
    def __init__(
        self,
        map_cell_service: MapCellService,
        world_service: WorldService | None = None,
    ) -> None:
        self._map_cells = map_cell_service
        self._worlds = world_service

    async def _cell_size_m(self, world_uid: str) -> int | None:
        if self._worlds is None:
            return None
        world = await self._worlds.find_by_id(world_uid)
        return world.map_cell_size_m if world is not None else None

    async def render_world_grid(
        self,
        world_uid: str,
        *,
        locations: list[NamedLocation] | None = None,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
        mark_locations: bool = True,
    ) -> dict[str, str]:
        cells = await self._map_cells.get_all(world_uid)
        cell_size_m_val = await self._cell_size_m(world_uid)
        renderer = WorldGridRenderer(
            cells,
            locations=locations,
            cell_size_m=cell_size_m_val,
        )
        if gx0 is not None and gy0 is not None and gx1 is not None and gy1 is not None:
            ascii_grid = renderer.render_bbox(gx0, gy0, gx1, gy1, mark_location=mark_locations)
        else:
            ascii_grid = renderer.render(mark_location=mark_locations)
        return {
            "ascii": ascii_grid,
            "legend": WorldGridRenderer.render_legend(mark_location=mark_locations),
            "mark_locations": mark_locations,
            "cell_size_m": cell_size_m_val,
        }

    async def render_world_tile_grids(self, world_uid: str) -> dict[str, object]:
        cells = await self._map_cells.get_all(world_uid)
        cell_size_m_val = await self._cell_size_m(world_uid)
        if not cell_size_m_val:
            return {"world_uid": world_uid, "tiles": {}}
        tiles: dict[str, dict[str, object]] = {}
        by_tile: dict[tuple[int, int], list] = {}
        for cell in cells:
            if cell.system_building_element:
                continue
            gx = cell.x // cell_size_m_val
            gy = cell.y // cell_size_m_val
            by_tile.setdefault((gx, gy), []).append(cell)
        for (gx, gy), tile_cells in sorted(by_tile.items()):
            renderer = WorldTileGridRenderer(
                tile_cells,
                tile_gx=gx,
                tile_gy=gy,
                cell_size_m=cell_size_m_val,
            )
            levels = renderer.render_all_levels()
            key = f"Gx{gx}_Gy{gy}"
            tiles[key] = {
                "tile_gx": gx,
                "tile_gy": gy,
                "z_levels": sorted(int(z) for z in levels),
                "levels": {str(z): txt for z, txt in sorted(levels.items())},
                "legend": WorldTileGridRenderer.render_legend(),
            }
        return {
            "world_uid": world_uid,
            "cell_size_m": cell_size_m_val,
            "tile_keys": list(tiles.keys()),
            "tiles": tiles,
        }

    async def render_all_location_grids(self, world_uid: str) -> dict[str, object]:
        cells = await self._map_cells.get_all(world_uid)
        cell_size_m_val = await self._cell_size_m(world_uid)
        location_uids = sorted({
            cell.location_uid
            for cell in cells
            if cell.location_uid
        })
        outdoor_legend = WorldGridRenderer.render_legend()
        locations: dict[str, dict[str, object]] = {}
        for location_uid in location_uids:
            renderer = LocationGridRenderer(
                cells,
                location_uid,
                cell_size_m=cell_size_m_val,
            )
            levels_raw = renderer.render_all_levels()
            levels = {
                str(z): grid
                for z, grid in sorted(levels_raw.items())
                if grid.strip()
            }
            indoor = bool(renderer._indoor_cells())
            locations[location_uid] = {
                "indoor": indoor,
                "z_levels": sorted(int(z) for z in levels),
                "levels": levels,
                "legend": LocationGridRenderer.render_legend(indoor=indoor),
            }
        return {
            "world_uid": world_uid,
            "cell_size_m": cell_size_m_val,
            "location_uids": location_uids,
            "locations": locations,
            "outdoor_legend": outdoor_legend,
        }

    async def render_location_grid(
        self,
        world_uid: str,
        location_uid: str,
        *,
        z: int | None = None,
    ) -> dict[str, str | dict[int, str]]:
        cells = await self._map_cells.get_all(world_uid)
        cell_size_m_val = await self._cell_size_m(world_uid)
        renderer = LocationGridRenderer(
            cells,
            location_uid,
            cell_size_m=cell_size_m_val,
        )
        indoor = bool(renderer._indoor_cells())
        legend = LocationGridRenderer.render_legend(indoor=indoor)
        if z is not None:
            return {
                "ascii": renderer.render_level(z),
                "legend": legend,
                "z": z,
                "cell_size_m": cell_size_m_val,
            }
        levels = renderer.render_all_levels()
        return {
            "levels": levels,
            "legend": legend,
            "indoor": indoor,
            "cell_size_m": cell_size_m_val,
        }
