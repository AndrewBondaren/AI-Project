"""Pack-backed ASCII map render — PackRenderReadFacade → pack renderers → payloads."""

from __future__ import annotations

from app.application.worldData.pack.read.packRenderReadFacade import PackRenderReadFacade
from app.application.worldData.render.locationTerrainPackRenderer import LocationTerrainPackRenderer
from app.application.worldData.render.renderPayloads import (
    LEVEL_LIGHT,
    LocationEntryPayload,
    LocationGridPayload,
    LocationGridsPayload,
    WorldGridPayload,
    WorldTileEntryPayload,
    WorldTileGridsPayload,
)
from app.application.worldData.render.worldMapPackRenderer import WorldMapPackRenderer
from app.db.models.world import World


class PackMapGridRender:
    def __init__(self, render_read: PackRenderReadFacade) -> None:
        self._read = render_read

    def _world_renderer(self, world: World) -> WorldMapPackRenderer | None:
        source = self._read.try_world_map_source(world)
        if source is None:
            return None
        return WorldMapPackRenderer(
            source.tiles,
            tile_size_m=source.tile_size_m,
            pins=source.pins,
        )

    def render_world_grid(
        self,
        world: World,
        *,
        gx0: int | None = None,
        gy0: int | None = None,
        gx1: int | None = None,
        gy1: int | None = None,
        mark_locations: bool = True,
    ) -> WorldGridPayload:
        """Pack world ASCII — L0 light-mask mosaic (SoT), not macro aggregate."""
        renderer = self._world_renderer(world)
        if renderer is None:
            ascii_grid = ""
        else:
            ascii_grid = renderer.render_light_mask_mosaic(
                gx0=gx0,
                gy0=gy0,
                gx1=gx1,
                gy1=gy1,
                mark_location=mark_locations,
            )
        return WorldGridPayload(
            ascii=ascii_grid,
            legend=WorldMapPackRenderer.render_legend(mark_location=mark_locations),
            mark_locations=mark_locations,
            cell_size_m=world.map_cell_size_m,
            read_path="pack",
            read_mode="world_map_light_mask",
        )

    def render_world_tile_grids(self, world: World) -> WorldTileGridsPayload:
        renderer = self._world_renderer(world)
        tiles: dict[str, WorldTileEntryPayload] = {}
        if renderer is not None:
            for (gx, gy), ascii_grid in renderer.render_all_tile_light_grids(
                mark_location=True,
            ).items():
                key = f"Gx{gx}_Gy{gy}"
                tiles[key] = WorldTileEntryPayload(
                    tile_gx=gx,
                    tile_gy=gy,
                    levels={LEVEL_LIGHT: ascii_grid},
                    z_levels=[LEVEL_LIGHT],
                    legend=WorldMapPackRenderer.render_legend(mark_location=True),
                    grid_kind="world_map_light",
                )
        return WorldTileGridsPayload(
            world_uid=world.world_uid,
            cell_size_m=world.map_cell_size_m,
            tiles=tiles,
            read_path="pack",
            read_mode="world_map_light_mask",
        )

    def render_all_location_grids(self, world: World) -> LocationGridsPayload:
        location_uids = self._read.location_uids_with_terrain(world)
        locations: dict[str, LocationEntryPayload] = {}
        legend = LocationTerrainPackRenderer.render_legend()
        for location_uid in location_uids:
            source = self._read.try_location_terrain(world, location_uid)
            if source is None:
                continue
            renderer = LocationTerrainPackRenderer(
                source.chunk,
                volume=source.volume,
                location_uid=source.location_uid,
            )
            levels = renderer.render_all_levels()
            locations[location_uid] = LocationEntryPayload(
                indoor=False,
                levels=levels,
                z_levels=list(levels.keys()),
                legend=legend,
                read_mode="location_terrain",
            )
        pins = [
            p.model_dump()
            for p in self._read.read_locations_index(world).locations
        ]
        return LocationGridsPayload(
            world_uid=world.world_uid,
            cell_size_m=world.map_cell_size_m,
            location_uids=location_uids,
            locations=locations,
            outdoor_legend=legend,
            read_path="pack",
            read_mode="location_terrain",
            locations_index_pins=pins,
        )

    def render_location_grid(
        self,
        world: World,
        location_uid: str,
        *,
        z: int | None = None,
    ) -> LocationGridPayload:
        source = self._read.try_location_terrain(world, location_uid)
        legend = LocationTerrainPackRenderer.render_legend()
        if source is None:
            return LocationGridPayload(
                legend=legend,
                cell_size_m=world.map_cell_size_m,
                read_path="pack",
                read_mode="location_terrain_missing",
                indoor=False,
                levels={},
            )
        renderer = LocationTerrainPackRenderer(
            source.chunk,
            volume=source.volume,
            location_uid=source.location_uid,
        )
        if z is not None:
            return LocationGridPayload(
                legend=legend,
                cell_size_m=world.map_cell_size_m,
                read_path="pack",
                read_mode="location_terrain",
                ascii=renderer.render_level(z),
                z=z,
            )
        levels = renderer.render_all_levels()
        return LocationGridPayload(
            legend=legend,
            cell_size_m=world.map_cell_size_m,
            read_path="pack",
            read_mode="location_terrain",
            indoor=False,
            levels=levels,
        )
