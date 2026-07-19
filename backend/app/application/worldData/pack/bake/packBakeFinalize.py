"""Finalize pack metadata on world row after bake."""

from __future__ import annotations

from app.application.worldData.pack.bake.packBakeLog import log_pack_finalize
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.worldService import WorldService
from app.db.models.world import World


async def finalize_pack_on_world(
    world_service: WorldService,
    world: World,
    writer: WorldPackWriter,
    *,
    read_context: PackReadContext | None = None,
) -> World:
    writer.recalc_manifest_counters()
    writer.save_manifest()
    if read_context is not None:
        read_context.invalidate_pack(world)
    manifest = writer.manifest
    result = await world_service.update(
        world.world_uid,
        {
            "terrain_pack_path": writer.pack_storage_path(),
            "terrain_pack_hash": manifest.content_hash,
            "world_map_cells_per_tile": manifest.world_map_cells_per_tile,
        },
    )
    log_pack_finalize(
        world.world_uid,
        pack_path=writer.pack_storage_path(),
        content_hash=manifest.content_hash,
    )
    return result.world
