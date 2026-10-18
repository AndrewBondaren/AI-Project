"""Unified map cell read path — Pack + patches + merge (WP-20 gameplay)."""

from __future__ import annotations

import logging

from app.application.worldData.pack.read.terrainContributions import column_surface, fine_terrain_contribution

from app.application.worldData.generators.terrain.worldMapSettings import n_base, terrain_chunk_columns, world_z_min
from app.application.worldData.pack.read.settlementStructureRaster import SettlementStructureRaster
from app.application.worldData.pack.read.worldMapPackReader import WorldMapPackReader
from app.application.worldData.pack.read.packMapHelpers import tile_index, world_map_cell_span
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.read.mapCellFromMerged import merged_view_to_map_cell
from app.application.worldData.mapCells.patchStoreService import PatchStoreService
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.bake.layerPriority import MapLayerKind
from app.dataModel.worldPack.wire.mergeMapCells import CellContribution, LayerSlice, MergedCellView
from app.application.worldData.pack.read.regionStateOverlay import CellLayers, RegionStateOverlay
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.dataModel.worldPack.meta.worldPackManifest import ChunkRefineRole
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)


class MapCellQueryFacade:
    """Gameplay read: ``get_cell`` / ``get_scene_volume`` with WP-20 merge."""

    def __init__(
        self,
        context: PackReadContext,
        patch_store: PatchStoreService,
        world_map_reader: WorldMapPackReader,
        *,
        city_raster: SettlementStructureRaster | None = None,
        region_state_repo: IRegionStateRepository | None = None,
    ) -> None:
        self._overlay = RegionStateOverlay(region_state_repo)
        self._ctx = context
        self._patches = patch_store
        self._world_map = world_map_reader
        self._city = city_raster or SettlementStructureRaster(context)

    def has_pack(self) -> bool:
        return self._ctx.has_pack()

    def has_pack_for(self, world: World) -> bool:
        return self._ctx.has_pack_for(world)

    async def get_cell(
        self,
        world: World,
        x: int,
        y: int,
        z: int,
        *,
        patch: CellContribution | None = None,
    ) -> MergedCellView:
        if patch is None:
            patch = await self._patches.get_patch_at(world.world_uid, x, y, z)
        views = await self.merge_layer_batches(world, {(x, y, z): self._layers_at(world, x, y, z, patch)})
        return views[0]

    async def merge_layer_batches(self, world: World, cells: CellLayers) -> list[MergedCellView]:
        entries = (self._ctx.reader_for(world).manifest.wilderness_region_entries
                   if self._ctx.has_pack_for(world) else [])
        views = await self._overlay.merge(world, cells, entries)
        return [self._world_map.apply_climate(world, view) for view in views]

    async def get_cells(self, world: World,
                        patches: dict[tuple[int, int, int], CellContribution | None]) -> list[MergedCellView]:
        """Read a coordinate batch with an already loaded patch snapshot."""
        cells = {coord: self._layers_at(world, *coord, patch) for coord, patch in patches.items()}
        return await self.merge_layer_batches(world, cells)

    def _layers_at(self, world: World, x: int, y: int, z: int,
                   patch: CellContribution | None = None) -> list[LayerSlice]:
        layers = [LayerSlice(kind=MapLayerKind.PATCH, cell=patch)] if patch is not None else []
        tile_size = world_map_cell_span(world)
        gx, lx = tile_index(x, tile_size)
        gy, ly = tile_index(y, tile_size)
        chunk_cols = terrain_chunk_columns(world)
        cx, col_lx = divmod(lx, chunk_cols)
        cy, col_ly = divmod(ly, chunk_cols)

        manifest = self._ctx.reader_for(world).manifest if self._ctx.has_pack_for(world) else None
        chunk_role = self._chunk_refine_role(manifest, gx, gy, cx, cy)

        reader = self._ctx.reader_for(world)
        if reader.chunk_exists(gx, gy, cx, cy):
            try:
                chunk = reader.read_wilderness_chunk(gx, gy, cx, cy)
                kind = self._chunk_layer_kind(chunk_role)
                contrib = fine_terrain_contribution(chunk, col_lx, col_ly, x, y, z)
                if contrib is not None:
                    layers.append(LayerSlice(kind=kind, cell=contrib))
            except FileNotFoundError:
                logger.debug(
                    "missing wilderness chunk world=%s tile=%d,%d chunk=%d,%d",
                    world.world_uid, gx, gy, cx, cy,
                )

        city = self._city.contribution(world, x, y, z)
        if city is not None:
            layers.append(LayerSlice(kind=MapLayerKind.CITY_STRUCTURE, cell=city))

        if manifest is not None:
            for loc in manifest.location_terrain_entries:
                if not loc.territory_volume.contains(x, y, z) or not loc.terrain_path:
                    continue
                try:
                    loc_chunk = reader.read_location_terrain(loc.location_uid)
                    lx_loc = x - loc.territory_volume.x0
                    ly_loc = y - loc.territory_volume.y0
                    contrib = fine_terrain_contribution(loc_chunk, lx_loc, ly_loc, x, y, z)
                    if contrib is not None:
                        layers.append(LayerSlice(kind=MapLayerKind.LOCATION, cell=contrib))
                        break
                except FileNotFoundError:
                    logger.debug("missing location terrain world=%s loc=%s", world.world_uid, loc.location_uid)
                    continue

        world_map = self._world_map.world_map_contribution(world, gx, gy, lx, ly, x, y, z)
        if world_map is not None:
            layers.append(LayerSlice(kind=MapLayerKind.WORLD_MAP, cell=world_map))

        return layers

    async def get_scene_volume(
        self,
        world: World,
        x: int,
        y: int,
        z: int,
        *,
        xy_radius: int = SceneVolumePolicy.canonical_defaults().scene_xy_radius,
        z_below: int | None = None,
        z_above: int = SceneVolumePolicy.canonical_defaults().scene_z_above,
    ) -> list[MergedCellView]:
        depth = z_below if z_below is not None else n_base(world)
        z_lo = max(world_z_min(world), z - depth)
        z_hi = z + z_above
        r = max(0, xy_radius)
        patch_map = await self._patches.get_patches_map_in_bbox(
            world.world_uid, x - r, x + r, y - r, y + r, z_lo, z_hi,
        )
        patches = {(cx, cy, cz): patch_map.get((cx, cy, cz))
                 for cx in range(x - r, x + r + 1)
                 for cy in range(y - r, y + r + 1)
                 for cz in range(z_lo, z_hi + 1)}
        return [view for view in await self.get_cells(world, patches) if view.has_any_data()]

    async def get_scene_volume_as_map_cells(
        self,
        world: World,
        x: int,
        y: int,
        z: int,
        **kwargs,
    ) -> list[MapCell]:
        views = await self.get_scene_volume(world, x, y, z, **kwargs)
        return [merged_view_to_map_cell(world.world_uid, view) for view in views]

    def invalidate_city_structure(self) -> None:
        self._city.invalidate()

    async def get_footprint_terrain(
        self,
        world: World,
        *,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        location_uid: str | None = None,
    ) -> list[MapCell]:
        """Surface columns in AABB for settlement assembler — no city layer, no z-flood."""
        cells_by_xy: dict[tuple[int, int], MapCell] = {}
        region_uids: dict[tuple[int, int], str | None] = {}
        if self._ctx.has_pack_for(world):
            reader = self._ctx.reader_for(world)
            manifest = reader.manifest
            loc_uid = location_uid
            entries = manifest.location_terrain_entries
            if loc_uid:
                entries = [e for e in entries if e.location_uid == loc_uid]
            for loc in entries:
                vol = loc.territory_volume
                if vol.x1 < x0 or vol.x0 > x1 or vol.y1 < y0 or vol.y0 > y1:
                    continue
                if not loc.terrain_path:
                    continue
                try:
                    chunk = reader.read_location_terrain(loc.location_uid)
                except FileNotFoundError:
                    continue
                for column in chunk.columns:
                    wx = vol.x0 + column.lx
                    wy = vol.y0 + column.ly
                    if wx < x0 or wx > x1 or wy < y0 or wy > y1:
                        continue
                    surface = column_surface(column)
                    if surface is None:
                        continue
                    sz, terrain, material = surface
                    region_uids[(wx, wy)] = column.region_uid
                    cells_by_xy[(wx, wy)] = MapCell(
                        world_uid=world.world_uid,
                        x=wx,
                        y=wy,
                        z=sz,
                        system_terrain=terrain,
                        system_material=material,
                        location_uid=loc.location_uid,
                    )
            if not cells_by_xy:
                tile_size = world_map_cell_span(world)
                gx0, _ = tile_index(x0, tile_size)
                gx1, _ = tile_index(x1, tile_size)
                gy0, _ = tile_index(y0, tile_size)
                gy1, _ = tile_index(y1, tile_size)
                for gx in range(gx0, gx1 + 1):
                    for gy in range(gy0, gy1 + 1):
                        for cell in self._world_map.surface_cells_for_tile(
                            world, gx, gy, tile_size,
                        ):
                            if x0 <= cell.x <= x1 and y0 <= cell.y <= y1:
                                cells_by_xy[(cell.x, cell.y)] = cell

        out = list(cells_by_xy.values())
        if not out:
            return out
        z_lo = min(c.z for c in out)
        z_hi = max(c.z for c in out)
        patch_map = await self._patches.get_patches_map_in_bbox(
            world.world_uid, x0, x1, y0, y1, z_lo, z_hi,
        )
        cells: CellLayers = {}
        tile_size = world_map_cell_span(world)
        for cell in out:
            key = (cell.x, cell.y, cell.z)
            if (cell.x, cell.y) in region_uids:
                base = CellContribution(x=cell.x, y=cell.y, z=cell.z,
                                        system_terrain=cell.system_terrain,
                                        system_material=cell.system_material,
                                        location_uid=cell.location_uid,
                                        region_uid=region_uids[(cell.x, cell.y)])
                kind = MapLayerKind.LOCATION
            else:
                gx, lx = tile_index(cell.x, tile_size)
                gy, ly = tile_index(cell.y, tile_size)
                base = self._world_map.world_map_contribution(
                    world, gx, gy, lx, ly, cell.x, cell.y, cell.z)
                kind = MapLayerKind.WORLD_MAP
            cells[key] = [LayerSlice(kind=kind, cell=base),
                          LayerSlice(kind=MapLayerKind.PATCH, cell=patch_map.get(key))]
        return [merged_view_to_map_cell(world.world_uid, view)
                for view in await self.merge_layer_batches(world, cells)]

    @staticmethod
    def _chunk_layer_kind(role: ChunkRefineRole | None) -> MapLayerKind:
        if role == "scene":
            return MapLayerKind.PLAYER_SCENE
        if role == "path":
            return MapLayerKind.PLAYER_PATH
        if role == "location":
            return MapLayerKind.LOCATION
        return MapLayerKind.WILDERNESS

    @staticmethod
    def _chunk_refine_role(manifest, gx: int, gy: int, cx: int, cy: int) -> ChunkRefineRole | None:
        if manifest is None:
            return None
        ref = manifest.chunk_ref(gx, gy, cx, cy)
        return ref.refine_role if ref is not None else None
