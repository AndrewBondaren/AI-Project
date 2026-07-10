"""L0 light bake per macro-tile — WP-15."""

from __future__ import annotations

from app.application.jsonValidation import terrain_system_keys
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
    prepare_surface_terrain_context,
)
from app.application.worldData.generators.terrain.terrainZ import surface_terrain_at_z
from app.application.worldData.pack.l0HydrologyMap import l0_hydro_role_from_cell
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class L0BakeOrchestrator:
    def bake_tile(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        gx: int,
        gy: int,
        writer: WorldPackWriter,
        *,
        cells_per_side: int | None = None,
    ) -> int:
        tile_m = cell_size_m(world)
        side = cells_per_side or resolve_world_map_cells_per_tile(
            tile_m,
            world.world_map_cells_per_tile,
        )
        terrain_set = terrain_system_keys(world)
        cells: list[WorldMapCellWire] = []
        for ty in range(side):
            for tx in range(side):
                xm = gx * tile_m + tx * tile_m // side
                ym = gy * tile_m + ty * tile_m // side
                surface_z = int(surface_ctx.coarse_surface_z.get((xm, ym), 0))
                hydro_cell = surface_ctx.coarse_hydro.get((xm, ym))
                system_terrain = surface_terrain_at_z(surface_z, terrain_set)
                cells.append(
                    WorldMapCellWire(
                        tx=tx,
                        ty=ty,
                        surface_z=surface_z,
                        system_terrain=system_terrain,
                        hydrology_role=l0_hydro_role_from_cell(hydro_cell),
                    ),
                )
        writer.write_l0_world_map(gx, gy, cells, cells_per_side=side)
        return len(cells)

    def bake_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        tiles: list[tuple[int, int]],
        **prepare_kwargs,
    ) -> int:
        surface_ctx = prepare_surface_terrain_context(world, locations, **prepare_kwargs)
        if surface_ctx is None:
            return 0
        tile_m = cell_size_m(world)
        side = resolve_world_map_cells_per_tile(tile_m, world.world_map_cells_per_tile)
        writer.sync_world_metadata(world, cells_per_side=side)
        total = 0
        for gx, gy in tiles:
            total += self.bake_tile(world, surface_ctx, gx, gy, writer, cells_per_side=side)
        writer.manifest.bake_mode = "light"
        writer.recalc_manifest_counters()
        writer.save_manifest()
        return total
