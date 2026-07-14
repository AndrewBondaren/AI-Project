"""Legacy MapCell-backed ASCII map render — debug only."""

from __future__ import annotations

from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.render.locationGridRenderer import LocationGridRenderer
from app.application.worldData.render.renderPayloads import (
    LocationEntryPayload,
    LocationGridPayload,
    LocationGridsPayload,
    WorldGridPayload,
    WorldTileEntryPayload,
    WorldTileGridsPayload,
)
from app.application.worldData.render.worldGridRenderer import WorldGridRenderer
from app.application.worldData.render.worldTileGridRenderer import WorldTileGridRenderer
from app.db.models.world import World


class LegacyMapGridRender:
    def __init__(self, map_cell_service: MapCellService) -> None:
        self._map_cells = map_cell_service

    async def render_world_grid(
        self,
        world: World,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
        mark_locations: bool = True,
    ) -> WorldGridPayload:
        cells = await self._map_cells.get_all_for_read(world)
        renderer = WorldGridRenderer(cells, cell_size_m=world.map_cell_size_m)
        if gx0 is not None and gy0 is not None and gx1 is not None and gy1 is not None:
            ascii_grid = renderer.render_bbox(gx0, gy0, gx1, gy1, mark_location=mark_locations)
        else:
            ascii_grid = renderer.render(mark_location=mark_locations)
        return WorldGridPayload(
            ascii=ascii_grid,
            legend=WorldGridRenderer.render_legend(mark_location=mark_locations),
            mark_locations=mark_locations,
            cell_size_m=world.map_cell_size_m,
            read_path="legacy",
            read_mode="map_cells",
        )

    async def render_world_tile_grids(self, world: World) -> WorldTileGridsPayload:
        cell_size_m_val = world.map_cell_size_m
        cells = await self._map_cells.get_all_for_read(world)
        tiles: dict[str, WorldTileEntryPayload] = {}
        if not cell_size_m_val:
            return WorldTileGridsPayload(
                world_uid=world.world_uid,
                cell_size_m=0,
                tiles={},
                read_path="legacy",
                read_mode="map_cells_tiles",
            )
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
            levels_raw = renderer.render_all_levels()
            levels = {str(z): txt for z, txt in sorted(levels_raw.items())}
            key = f"Gx{gx}_Gy{gy}"
            tiles[key] = WorldTileEntryPayload(
                tile_gx=gx,
                tile_gy=gy,
                levels=levels,
                z_levels=sorted(int(z) for z in levels_raw),
                legend=WorldTileGridRenderer.render_legend(),
            )
        return WorldTileGridsPayload(
            world_uid=world.world_uid,
            cell_size_m=cell_size_m_val,
            tiles=tiles,
            read_path="legacy",
            read_mode="map_cells_tiles",
        )

    async def render_all_location_grids(self, world: World) -> LocationGridsPayload:
        cells = await self._map_cells.get_all_for_read(world)
        cell_size_m_val = world.map_cell_size_m
        location_uids = sorted({
            cell.location_uid
            for cell in cells
            if cell.location_uid
        })
        outdoor_legend = WorldGridRenderer.render_legend()
        locations: dict[str, LocationEntryPayload] = {}
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
            locations[location_uid] = LocationEntryPayload(
                indoor=indoor,
                levels=levels,
                z_levels=sorted(int(z) for z in levels),
                legend=LocationGridRenderer.render_legend(indoor=indoor),
            )
        return LocationGridsPayload(
            world_uid=world.world_uid,
            cell_size_m=cell_size_m_val,
            location_uids=location_uids,
            locations=locations,
            outdoor_legend=outdoor_legend,
            read_path="legacy",
            read_mode="map_cells",
        )

    async def render_location_grid(
        self,
        world: World,
        location_uid: str,
        *,
        z: int | None = None,
    ) -> LocationGridPayload:
        cells = await self._map_cells.get_all_for_read(world)
        cell_size_m_val = world.map_cell_size_m
        renderer = LocationGridRenderer(
            cells,
            location_uid,
            cell_size_m=cell_size_m_val,
        )
        indoor = bool(renderer._indoor_cells())
        legend = LocationGridRenderer.render_legend(indoor=indoor)
        if z is not None:
            return LocationGridPayload(
                legend=legend,
                cell_size_m=cell_size_m_val,
                read_path="legacy",
                read_mode="map_cells",
                ascii=renderer.render_level(z),
                z=z,
            )
        levels_raw = renderer.render_all_levels()
        levels = {str(z_key): grid for z_key, grid in levels_raw.items()}
        return LocationGridPayload(
            legend=legend,
            cell_size_m=cell_size_m_val,
            read_path="legacy",
            read_mode="map_cells",
            indoor=indoor,
            levels=levels,
        )
