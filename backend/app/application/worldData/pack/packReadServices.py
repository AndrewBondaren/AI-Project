"""Factory for pack read facades sharing one ``PackReadContext``."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.packDebugReadFacade import PackDebugReadFacade
from app.application.worldData.pack.packL0Reader import PackL0Reader
from app.application.worldData.pack.packLoadingProgressFacade import PackLoadingProgressFacade
from app.application.worldData.pack.packReadContext import PackReadContext
from app.application.worldData.patchStoreService import PatchStoreService


@dataclass(frozen=True)
class PackReadServices:
    context: PackReadContext
    gameplay: MapCellQueryFacade
    debug: PackDebugReadFacade
    loading: PackLoadingProgressFacade


def build_pack_read_services(
    world_uid: str,
    patches: PatchStoreService,
    *,
    db_path: str,
) -> PackReadServices:
    context = PackReadContext(world_uid, db_path=db_path)
    l0 = PackL0Reader(context)
    debug = PackDebugReadFacade(context, patches, l0)
    gameplay = MapCellQueryFacade(context, patches, l0)
    debug.bind_gameplay(gameplay)
    loading = PackLoadingProgressFacade(context)
    return PackReadServices(context=context, gameplay=gameplay, debug=debug, loading=loading)
