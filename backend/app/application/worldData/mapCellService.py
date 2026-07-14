"""map_cell_patches CRUD and layer upsert — pack reads via MapCellReadService."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, replace

from typing import TYPE_CHECKING, Protocol

from app.api.schemas.imports import ImportResult
from app.application.import_helpers import import_list
from app.application.worldData.generators.terrain.worldMapSettings import n_base, world_z_min
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.application.worldData.pack.read.patchCellContribution import patch_kind_for_save_pass
from app.dataModel.worldPack.mapCellPatchLayerKind import MapCellPatchLayerKind
from app.db.models.mapCell import MapCell
from app.db.models.world import World
from app.db.repositories.iMapCellRepository import IMapCellRepository

if TYPE_CHECKING:
    from app.application.worldData.pack.read.packReadServices import PackReadServices

logger = logging.getLogger(__name__)

LayerKind = str  # "terrain" | "climate" | "ore" | "cave"

PACK_LEGACY_GENERATE_MSG = (
    "Pack-backed world: terrain skeleton is in World Pack. "
    "Use POST /worlds/{uid}/map/pack/bake for terrain; patch layers via save_pass only."
)


class MapCellReadServiceFactory(Protocol):
    def __call__(self, world_uid: str): ...


class MapCellService:
    """map_cell_patches CRUD and layer upsert — no terrain generation orchestration (MR-7).

Pack-backed reads delegate to ``MapCellReadService`` (gameplay / debug / loading facades).
"""

    def __init__(
        self,
        repo: IMapCellRepository,
        *,
        read_service_factory: MapCellReadServiceFactory | None = None,
    ) -> None:
        self._repo = repo
        self._read_service_factory = read_service_factory

    @asynccontextmanager
    async def bulk_persist_session(self):
        """TR-PERF-2: defer commit across multiple save_pass calls."""
        async with self._repo.persist_session():
            yield

    async def has_world_cells(self, world_uid: str) -> bool:
        return await self._repo.has_world_cells(world_uid)

    def _read(self, world_uid: str):
        if self._read_service_factory is None:
            return None
        return self._read_service_factory(world_uid)

    def uses_pack_read(self, world: World) -> bool:
        read = self._read(world.world_uid)
        return read is not None and read.has_pack_for(world)

    def pack_read_services(self, world: World) -> PackReadServices | None:
        """Pack facades when this world has a pack on disk; else ``None``."""
        read = self._read(world.world_uid)
        if read is None or not read.has_pack_for(world):
            return None
        return read.pack

    async def get_all_for_read(self, world: World) -> list[MapCell]:
        read = self._read(world.world_uid)
        if read is not None and read.has_pack_for(world):
            return await read.pack.debug.get_debug_export_cells(world)
        return await self.get_all(world.world_uid)

    async def get_tile_cells_for_read(self, world: World, gx: int, gy: int) -> list[MapCell]:
        read = self._read(world.world_uid)
        if read is not None and read.has_pack_for(world):
            return read.pack.debug.get_world_map_tile_sample_cells(world, gx, gy)
        cell_m = world.map_cell_size_m
        x0, y0 = gx * cell_m, gy * cell_m
        x1, y1 = x0 + cell_m - 1, y0 + cell_m - 1
        all_cells = await self.get_all(world.world_uid)
        return [
            c for c in all_cells
            if x0 <= c.x <= x1 and y0 <= c.y <= y1 and not c.system_building_element
        ]

    async def export_for_debug(self, world: World) -> dict:
        cells = await self.get_all_for_read(world)
        if self.uses_pack_read(world):
            return {
                "cells": [asdict(c) for c in cells],
                "read_path": "facade",
                "read_mode": "world_map_surface_merged_patches",
            }
        return {
            "cells": [asdict(c) for c in cells],
            "read_path": "patches",
            "read_mode": "patches_only",
        }

    def world_map_tile_coords(self, world: World) -> list[tuple[int, int]]:
        read = self._read(world.world_uid)
        if read is None or not read.has_pack_for(world):
            return []
        return read.pack.debug.world_map_tile_coords(world)

    async def get_all(self, world_uid: str) -> list[MapCell]:
        return await self._repo.get_by_world(world_uid)

    async def export(self, world_uid: str) -> list[dict]:
        cells = await self._repo.get_by_world(world_uid)
        return [asdict(c) for c in cells]

    async def import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult:
        def prepare(row: dict) -> MapCell:
            return MapCell(**{**row, "world_uid": world_uid})
        return await import_list(data, prepare, self._repo.upsert)

    async def clear(self, world_uid: str) -> None:
        await self._repo.delete_by_world(world_uid)

    async def get_location_uids_with_cells(self, world_uid: str) -> frozenset[str]:
        uids = await self._repo.get_location_uids_with_cells(world_uid)
        return frozenset(uids)

    async def has_column_cells(self, world_uid: str, x: int, y: int, *, world: World | None = None) -> bool:
        if world is not None:
            read = self._read(world.world_uid)
            if read is not None and read.has_pack_for(world):
                return await read.pack.debug.column_has_merged_data(world, x, y)
        return await self._repo.has_column_cells(world_uid, x, y)

    async def get_z_slice_for_read(
        self,
        world: World,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[MapCell]:
        read = self._read(world.world_uid)
        if read is not None and read.has_pack_for(world):
            return await read.pack.debug.get_merged_z_slice(
                world, x_min, x_max, y_min, y_max, z_min, z_max,
            )
        return await self.get_z_slice(
            world.world_uid, x_min, x_max, y_min, y_max, z_min, z_max,
        )

    def reject_legacy_generate_on_pack(self, world: World) -> None:
        if self.uses_pack_read(world):
            raise ValueError(PACK_LEGACY_GENERATE_MSG)

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
    ) -> list[MapCell]:
        """TR-LAZY-LOAD: 3D bbox around scene anchor for gameplay/debug."""
        read = self._read(world.world_uid)
        if read is not None and read.has_pack_for(world):
            return await read.pack.gameplay.get_scene_volume_as_map_cells(
                world, x, y, z,
                xy_radius=xy_radius,
                z_below=z_below,
                z_above=z_above,
            )
        depth = z_below if z_below is not None else n_base(world)
        z_lo = max(world_z_min(world), z - depth)
        z_hi = z + z_above
        r = max(0, xy_radius)
        return await self.get_z_slice(
            world.world_uid,
            x - r, x + r,
            y - r, y + r,
            z_lo, z_hi,
        )

    async def save_generated(self, cells: list[MapCell]) -> ImportResult:
        """Legacy: INSERT OR IGNORE — scope ``minimal_repair`` (lazy nodes).

        Insert matrix: ``docs/tz_terrain_generation.md`` § TR-PERF-DEBT-4.
        """
        inserted = await self._repo.insert_bulk_ignore(cells)
        return ImportResult(total=len(cells), succeeded=inserted, failed=0)

    async def save_settlement_surface(self, cells: list[MapCell]) -> ImportResult:
        """Outdoor settlement footprint — merge onto world surface grid."""
        stamped = [
            replace(c, layer_kind=MapCellPatchLayerKind.SETTLEMENT.value) for c in cells
        ]
        merged = await self._repo.upsert_settlement_surface(stamped)
        return ImportResult(total=len(cells), succeeded=merged, failed=0)

    def _stamp_layer_kind(self, cells: list[MapCell], layer: LayerKind) -> list[MapCell]:
        patch_kind = patch_kind_for_save_pass(layer).value
        return [replace(c, layer_kind=patch_kind) for c in cells]

    async def save_pass(
        self,
        cells: list[MapCell],
        layer: LayerKind,
        *,
        insert_only: bool = False,
    ) -> ImportResult:
        """Layer upsert; terrain ``insert_only`` → plain INSERT (TR-PERF-3).

        Backlog: replace flag with ``TerrainPersistScope`` — § TR-PERF-DEBT-3.
        Insert matrix: § TR-PERF-DEBT-4.
        """
        if layer == "terrain":
            if insert_only:
                raise ValueError("wilderness terrain persist rejected — use World Pack bake")
            n = await self._repo.upsert_terrain_skeleton(self._stamp_layer_kind(cells, layer))
        elif layer == "climate":
            n = await self._repo.upsert_climate_fields(self._stamp_layer_kind(cells, layer))
        elif layer == "ore":
            n = await self._repo.upsert_ore_markers(self._stamp_layer_kind(cells, layer))
        elif layer == "cave":
            n = await self._repo.upsert_cave_carve(self._stamp_layer_kind(cells, layer))
        else:
            raise ValueError(f"unknown layer kind: {layer}")
        return ImportResult(total=len(cells), succeeded=n, failed=0)

    async def get_z_slice(
        self,
        world_uid: str,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
        z_min: int,
        z_max: int,
    ) -> list[MapCell]:
        return await self._repo.get_z_slice(
            world_uid, x_min, x_max, y_min, y_max, z_min, z_max,
        )
