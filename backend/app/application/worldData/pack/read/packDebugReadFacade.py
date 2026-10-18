"""Debug world map / merged bbox read — MERGE-9 / REVIEW-5.

ASCII render I/O lives in ``PackRenderReadFacade`` (L0 + location_terrain + wilderness L2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.worldData.pack.read.mapCellFromMerged import merged_view_to_map_cell
from app.application.worldData.pack.read.worldMapPackReader import WorldMapPackReader
from app.application.worldData.pack.read.packMapHelpers import world_map_sample_index, tile_index, world_map_cell_span
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.mapCells.patchStoreService import PatchStoreService
from app.dataModel.worldPack.bake.layerPriority import MapLayerKind
from app.dataModel.worldPack.wire.mergeMapCells import LayerSlice
from app.db.models.mapCell import MapCell
from app.db.models.world import World

if TYPE_CHECKING:
    from app.application.worldData.mapCells.mapCellQueryFacade import MapCellQueryFacade


class PackDebugReadFacade:
    """World map coarse export and merged bbox probes — not gameplay scene merge."""

    def __init__(
        self,
        context: PackReadContext,
        patches: PatchStoreService,
        world_map: WorldMapPackReader,
        *,
        gameplay: MapCellQueryFacade | None = None,
    ) -> None:
        self._ctx = context
        self._patches = patches
        self._world_map = world_map
        self._gameplay = gameplay

    def bind_gameplay(self, gameplay: MapCellQueryFacade) -> None:
        self._gameplay = gameplay

    def world_map_tile_coords(self, world: World) -> list[tuple[int, int]]:
        if not self._ctx.has_pack_for(world):
            return []
        return [
            (t.gx, t.gy)
            for t in self._ctx.reader_for(world).manifest.tiles
            if t.world_map_path
        ]

    def get_world_map_surface_cells(self, world: World) -> list[MapCell]:
        if not self._ctx.has_pack_for(world):
            return []
        manifest = self._ctx.reader_for(world).manifest
        tile_size = world_map_cell_span(world)
        out: list[MapCell] = []
        for entry in manifest.tiles:
            if not entry.world_map_path:
                continue
            out.extend(self._world_map.surface_cells_for_tile(world, entry.gx, entry.gy, tile_size))
        return out

    def get_world_map_tile_sample_cells(self, world: World, gx: int, gy: int) -> list[MapCell]:
        if not self._ctx.has_pack_for(world):
            return []
        return self._world_map.surface_cells_for_tile(world, gx, gy, world_map_cell_span(world))

    async def get_debug_export_cells(self, world: World) -> list[MapCell]:
        """World map coarse surface + patches per ``(x,y,z)`` — ``read_mode=world_map_surface_merged_patches``."""
        if not self._ctx.has_pack_for(world):
            return []
        layers_by_key: dict[tuple[int, int, int], list[LayerSlice]] = {}
        for cell in self.get_world_map_surface_cells(world):
            tile_size = world_map_cell_span(world)
            gx, lx = tile_index(cell.x, tile_size)
            gy, ly = tile_index(cell.y, tile_size)
            contrib = self._world_map.world_map_contribution(
                world, gx, gy, lx, ly, cell.x, cell.y, cell.z)
            key = (cell.x, cell.y, cell.z)
            layers_by_key.setdefault(key, []).append(
                LayerSlice(kind=MapLayerKind.WORLD_MAP, cell=contrib),
            )
        for patch in await self._patches.get_all_patches(world.world_uid):
            key = (patch.x, patch.y, patch.z)
            layers_by_key.setdefault(key, []).append(
                LayerSlice(kind=MapLayerKind.PATCH, cell=patch),
            )
        if self._gameplay is None:
            raise RuntimeError("PackDebugReadFacade: gameplay facade not bound")
        return [merged_view_to_map_cell(world.world_uid, view)
                for view in await self._gameplay.merge_layer_batches(world, layers_by_key)
                if view.has_any_data()]

    async def get_merged_z_slice(
        self,
        world: World,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[MapCell]:
        """Full WP-20 merge in bbox — debug / export."""
        if self._gameplay is None:
            raise RuntimeError("PackDebugReadFacade: gameplay facade not bound")
        patch_map = await self._patches.get_patches_map_in_bbox(
            world.world_uid, x_min, x_max, y_min, y_max, z_min, z_max,
        )
        patches = {(x, y, z): patch_map.get((x, y, z))
                 for x in range(x_min, x_max + 1)
                 for y in range(y_min, y_max + 1)
                 for z in range(z_min, z_max + 1)}
        return [merged_view_to_map_cell(world.world_uid, view)
                for view in await self._gameplay.get_cells(world, patches)
                if view.has_any_data()]

    async def column_has_merged_data(self, world: World, x: int, y: int) -> bool:
        if not self._ctx.has_pack_for(world):
            return False
        if self._gameplay is None:
            raise RuntimeError("PackDebugReadFacade: gameplay facade not bound")
        tile_size = world_map_cell_span(world)
        gx, lx = tile_index(x, tile_size)
        gy, ly = tile_index(y, tile_size)
        reader = self._ctx.reader_for(world)
        try:
            side, _ = reader.read_world_map_tile(gx, gy)
        except FileNotFoundError:
            side = reader.manifest.world_map_cells_per_tile
        sample = self._world_map.sample_world_map(
            world, gx, gy,
            world_map_sample_index(lx, tile_size, side),
            world_map_sample_index(ly, tile_size, side),
        )
        if sample is None:
            return False
        merged = await self._gameplay.get_cell(world, x, y, sample.surface_z)
        return merged.has_any_data()
