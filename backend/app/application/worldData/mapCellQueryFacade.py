"""Unified map cell read path — Pack + patches + merge (WP-20 gameplay)."""

from __future__ import annotations

import logging

from app.application.worldData.generators.terrain.worldMapSettings import n_base, terrain_chunk_columns, world_z_min
from app.application.worldData.pack.worldMapPackReader import WorldMapPackReader
from app.application.worldData.pack.packMapHelpers import tile_index, world_tile_size_m
from app.application.worldData.pack.packReadContext import PackReadContext
from app.application.worldData.pack.mapCellFromMerged import merged_view_to_map_cell
from app.application.worldData.patchStoreService import PatchStoreService
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.layerPriority import MapLayerKind
from app.dataModel.worldPack.mergeMapCells import CellContribution, LayerSlice, MergedCellView, merge_layers
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
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
    ) -> None:
        self._ctx = context
        self._patches = patch_store
        self._world_map = world_map_reader

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
        layers: list[LayerSlice] = []
        patch_contrib = patch
        if patch_contrib is None:
            patch_contrib = await self._patches.get_patch_at(world.world_uid, x, y, z)
        if patch_contrib is not None:
            layers.append(LayerSlice(kind=MapLayerKind.PATCH, cell=patch_contrib))

        tile_size = world_tile_size_m(world)
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
                contrib = self._fine_terrain_contribution(chunk, col_lx, col_ly, x, y, z)
                if contrib is not None:
                    layers.append(LayerSlice(kind=kind, cell=contrib))
            except FileNotFoundError:
                logger.debug(
                    "missing wilderness chunk world=%s tile=%d,%d chunk=%d,%d",
                    world.world_uid, gx, gy, cx, cy,
                )

        if manifest is not None:
            for loc in manifest.location_terrain_entries:
                if not loc.territory_volume.contains(x, y, z) or not loc.terrain_path:
                    continue
                try:
                    loc_chunk = reader.read_location_terrain(loc.location_uid)
                    lx_loc = x - loc.territory_volume.x0
                    ly_loc = y - loc.territory_volume.y0
                    contrib = self._fine_terrain_contribution(loc_chunk, lx_loc, ly_loc, x, y, z)
                    if contrib is not None:
                        layers.append(LayerSlice(kind=MapLayerKind.LOCATION, cell=contrib))
                        break
                except FileNotFoundError:
                    logger.debug("missing location terrain world=%s loc=%s", world.world_uid, loc.location_uid)
                    continue

        world_map = self._world_map.world_map_contribution(world, gx, gy, lx, ly, x, y, z)
        if world_map is not None:
            layers.append(LayerSlice(kind=MapLayerKind.WORLD_MAP, cell=world_map))

        merged = merge_layers(x, y, z, layers)
        return self._world_map.apply_climate(world, merged)

    async def get_scene_volume(
        self,
        world: World,
        x: int,
        y: int,
        z: int,
        *,
        xy_radius: int = SceneVolumePolicy.canonical_defaults().scene_xy_radius,
        z_below: int | None = None,
        z_above: int = 0,
    ) -> list[MergedCellView]:
        depth = z_below if z_below is not None else n_base(world)
        z_lo = max(world_z_min(world), z - depth)
        z_hi = z + z_above
        r = max(0, xy_radius)
        patch_map = await self._patches.get_patches_map_in_bbox(
            world.world_uid, x - r, x + r, y - r, y + r, z_lo, z_hi,
        )
        out: list[MergedCellView] = []
        for cx in range(x - r, x + r + 1):
            for cy in range(y - r, y + r + 1):
                for cz in range(z_lo, z_hi + 1):
                    merged = await self.get_cell(
                        world, cx, cy, cz,
                        patch=patch_map.get((cx, cy, cz)),
                    )
                    if merged.has_any_data():
                        out.append(merged)
        return out

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

    @staticmethod
    def _chunk_layer_kind(role: ChunkRefineRole | None) -> MapLayerKind:
        if role == "scene":
            return MapLayerKind.PLAYER_SCENE
        if role == "path":
            return MapLayerKind.PLAYER_PATH
        return MapLayerKind.WILDERNESS

    @staticmethod
    def _chunk_refine_role(manifest, gx: int, gy: int, cx: int, cy: int) -> ChunkRefineRole | None:
        if manifest is None:
            return None
        ref = manifest.chunk_ref(gx, gy, cx, cy)
        return ref.refine_role if ref is not None else None

    def _fine_terrain_contribution(
        self,
        chunk,
        col_lx: int,
        col_ly: int,
        x: int,
        y: int,
        z: int,
    ) -> CellContribution | None:
        column = next((c for c in chunk.columns if c.lx == col_lx and c.ly == col_ly), None)
        if column is None:
            return None
        for run in column.runs:
            z_lo, z_hi = min(run.z0, run.z1), max(run.z0, run.z1)
            if z_lo <= z <= z_hi:
                return CellContribution(
                    x=x,
                    y=y,
                    z=z,
                    system_terrain=run.system_terrain,
                    system_material=run.system_material,
                )
        return None
