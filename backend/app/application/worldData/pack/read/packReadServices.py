"""Factory for pack read facades sharing one ``PackReadContext``."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.read.packDebugReadFacade import PackDebugReadFacade
from app.application.worldData.pack.read.worldMapPackReader import WorldMapPackReader
from app.application.worldData.pack.read.packFineTerrainReadFacade import PackFineTerrainReadFacade
from app.application.worldData.pack.read.packLoadingProgressFacade import PackLoadingProgressFacade
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.patchStoreService import PatchStoreService


@dataclass(frozen=True)
class PackReadServices:
    context: PackReadContext
    gameplay: MapCellQueryFacade
    debug: PackDebugReadFacade
    loading: PackLoadingProgressFacade
    fine_terrain_read: PackFineTerrainReadFacade


def build_pack_read_services(
    world_uid: str,
    patches: PatchStoreService,
    *,
    db_path: str,
) -> PackReadServices:
    context = PackReadContext(world_uid, db_path=db_path)
    world_map = WorldMapPackReader(context)
    debug = PackDebugReadFacade(context, patches, world_map)
    gameplay = MapCellQueryFacade(context, patches, world_map)
    debug.bind_gameplay(gameplay)
    loading = PackLoadingProgressFacade(context)
    fine_terrain_read = PackFineTerrainReadFacade(context, gameplay)
    return PackReadServices(
        context=context,
        gameplay=gameplay,
        debug=debug,
        loading=loading,
        fine_terrain_read=fine_terrain_read,
    )
