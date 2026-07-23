"""Pack-backed ASCII map render — PackRenderReadFacade → pack renderers → payloads."""

from __future__ import annotations

from app.application.worldData.generators.terrain.worldMapSettings import grid_bbox_padding
from app.application.worldData.pack.read.packRenderReadFacade import (
    PackRenderReadFacade,
    PackWorldMapRenderSource,
)
from app.application.worldData.render.locationTerrainPackRenderer import LocationTerrainPackRenderer
from app.application.worldData.render.renderPayloads import (
    LEVEL_HEIGHT,
    LEVEL_LIGHT,
    LocationEntryPayload,
    LocationGridPayload,
    LocationGridsPayload,
    WildernessTileGridPayload,
    WorldGridPayload,
    WorldTileEntryPayload,
    WorldTileGridsPayload,
)
from app.application.worldData.render.wildernessTilePackRenderer import WildernessTilePackRenderer
from app.application.worldData.render.worldMapPackRenderer import WorldMapPackRenderer
from app.dataModel.worldPack.worldBounds import WorldBounds
from app.db.models.world import World


class PackMapGridRender:
    def __init__(self, render_read: PackRenderReadFacade) -> None:
        self._read = render_read

    def _world_renderer(
        self,
        world: World,
        source: PackWorldMapRenderSource,
    ) -> WorldMapPackRenderer:
        return WorldMapPackRenderer(
            source.tiles,
            tile_size_m=source.tile_size_m,
            pins=source.pins,
        )

    @staticmethod
    def _resolve_mosaic_macro_bbox(
        world: World,
        source: PackWorldMapRenderSource,
        *,
        gx0: int | None,
        gy0: int | None,
        gx1: int | None,
        gy1: int | None,
    ) -> tuple[int | None, int | None, int | None, int | None]:
        """MLB-12: explicit query → declared world_bounds → pin AABB+padding → baked tiles."""
        if gx0 is not None and gy0 is not None and gx1 is not None and gy1 is not None:
            return gx0, gy0, gx1, gy1

        declared = WorldBounds.try_parse(getattr(world, "world_bounds", None))
        if declared is not None:
            return declared.x_min, declared.y_min, declared.x_max, declared.y_max

        pins = source.pins.locations
        if pins:
            cell_m = max(1, int(getattr(world, "map_cell_size_m", None) or source.tile_size_m))
            padding = grid_bbox_padding(world)
            xs = [int(p.map_x) // cell_m for p in pins]
            ys = [int(p.map_y) // cell_m for p in pins]
            return (
                min(xs) - padding,
                min(ys) - padding,
                max(xs) + padding,
                max(ys) + padding,
            )

        return None, None, None, None

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
        """Pack world ASCII — always L0 light-cell mosaic (WP-10 / MLB-12)."""
        source = self._read.try_world_map_source(world)
        if source is None:
            return WorldGridPayload(
                ascii="",
                legend=WorldMapPackRenderer.render_legend(mark_location=mark_locations),
                mark_locations=mark_locations,
                cell_size_m=world.map_cell_size_m,
                read_path="pack",
                read_mode="world_map_light_mask",
            )

        frame_gx0, frame_gy0, frame_gx1, frame_gy1 = self._resolve_mosaic_macro_bbox(
            world,
            source,
            gx0=gx0,
            gy0=gy0,
            gx1=gx1,
            gy1=gy1,
        )
        renderer = self._world_renderer(world, source)
        ascii_height, legend_height = renderer.render_light_height_mosaic(
            gx0=frame_gx0,
            gy0=frame_gy0,
            gx1=frame_gx1,
            gy1=frame_gy1,
        )
        ascii_grid = renderer.render_light_mask_mosaic(
            gx0=frame_gx0,
            gy0=frame_gy0,
            gx1=frame_gx1,
            gy1=frame_gy1,
            mark_location=mark_locations,
        )
        return WorldGridPayload(
            ascii=ascii_grid,
            legend=WorldMapPackRenderer.render_legend(mark_location=mark_locations),
            mark_locations=mark_locations,
            cell_size_m=world.map_cell_size_m,
            read_path="pack",
            read_mode="world_map_light_mask",
            ascii_height=ascii_height,
            legend_height=legend_height,
        )

    def render_world_tile_grids(self, world: World) -> WorldTileGridsPayload:
        """Canonical per-tile L0 mask smoke — always mosaic cells, never aggregate."""
        source = self._read.try_world_map_source(world)
        tiles: dict[str, WorldTileEntryPayload] = {}
        if source is not None:
            renderer = self._world_renderer(world, source)
            height_by_xy = renderer.render_all_tile_light_height_grids()
            for (gx, gy), ascii_grid in renderer.render_all_tile_light_grids(
                mark_location=True,
            ).items():
                key = f"Gx{gx}_Gy{gy}"
                levels = {LEVEL_LIGHT: ascii_grid}
                height = height_by_xy.get((gx, gy))
                if height:
                    levels[LEVEL_HEIGHT] = height
                tiles[key] = WorldTileEntryPayload(
                    tile_gx=gx,
                    tile_gy=gy,
                    levels=levels,
                    z_levels=list(levels.keys()),
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
            loc_source = self._read.try_location_terrain(world, location_uid)
            if loc_source is None:
                continue
            renderer = LocationTerrainPackRenderer(
                loc_source.chunk,
                volume=loc_source.volume,
                location_uid=loc_source.location_uid,
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
        loc_source = self._read.try_location_terrain(world, location_uid)
        legend = LocationTerrainPackRenderer.render_legend()
        if loc_source is None:
            return LocationGridPayload(
                legend=legend,
                cell_size_m=world.map_cell_size_m,
                read_path="pack",
                read_mode="location_terrain_missing",
                indoor=False,
                levels={},
            )
        renderer = LocationTerrainPackRenderer(
            loc_source.chunk,
            volume=loc_source.volume,
            location_uid=loc_source.location_uid,
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

    def render_wilderness_tile_grid(
        self,
        world: World,
        tile_gx: int,
        tile_gy: int,
        *,
        z: int | None = None,
        include_z_slices: bool = False,
    ) -> WildernessTileGridPayload:
        """L2 wilderness mosaic for one macro-tile (detailed-bake).

        Default levels = surface only (meter grid can be large). Pass ``z=`` for a
        slice, or ``include_z_slices=True`` for all run-endpoint levels.
        """
        legend = WildernessTilePackRenderer.render_legend()
        source = self._read.try_wilderness_tile(world, tile_gx, tile_gy)
        if source is None:
            return WildernessTileGridPayload(
                tile_gx=tile_gx,
                tile_gy=tile_gy,
                legend=legend,
                cell_size_m=world.map_cell_size_m,
                read_path="pack",
                read_mode="wilderness_tile_l2_missing",
            )
        renderer = WildernessTilePackRenderer(
            source.chunks,
            tile_gx=source.gx,
            tile_gy=source.gy,
            tile_size_m=source.tile_size_m,
        )
        if z is not None:
            ascii_grid = renderer.render_level(z)
            return WildernessTileGridPayload(
                tile_gx=tile_gx,
                tile_gy=tile_gy,
                legend=legend,
                cell_size_m=world.map_cell_size_m,
                read_path="pack",
                read_mode="wilderness_tile_l2",
                ascii=ascii_grid,
                z=z,
                chunks_listed=source.chunks_listed,
                chunks_loaded=source.chunks_loaded,
                column_count=renderer.column_count,
                wilderness_refine_status=source.wilderness_refine_status,
                z_levels=[z] if ascii_grid.strip() else [],
            )
        levels = renderer.render_all_levels(include_z_slices=include_z_slices)
        return WildernessTileGridPayload(
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            legend=legend,
            cell_size_m=world.map_cell_size_m,
            read_path="pack",
            read_mode="wilderness_tile_l2",
            levels=levels,
            z_levels=list(levels.keys()),
            chunks_listed=source.chunks_listed,
            chunks_loaded=source.chunks_loaded,
            column_count=renderer.column_count,
            wilderness_refine_status=source.wilderness_refine_status,
        )
