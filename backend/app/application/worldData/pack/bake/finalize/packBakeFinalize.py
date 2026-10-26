"""Finalize pack metadata on world row after bake."""

from __future__ import annotations

from copy import deepcopy

from app.application.worldData.pack.bake.packBakeLog import log_pack_finalize
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.errors import WorldDataValidationError
from app.application.worldData.registries.worldColumnWrite import apply_world_column
from app.application.worldData.registries.worldLookup import require_world
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


async def finalize_pack_on_world(
    world_repository: IWorldRepository,
    world: World,
    writer: WorldPackWriter,
    *,
    db_path: str,
    read_context: PackReadContext | None = None,
) -> World:
    if world.world_uid != writer.paths.world_uid or world.world_uid != writer.manifest.world_uid:
        raise WorldDataValidationError("pack finalization world identity mismatch")
    current = await require_world(world_repository, world.world_uid)
    old_root = WorldPackPaths.for_world(current, db_path).root
    updated = deepcopy(current)
    manifest = writer.manifest
    ctx = ResolveContext()
    # Prepare authored settings on a detached row before publishing the manifest.
    apply_world_column(updated, "world_map_cells_per_tile", manifest.world_map_cells_per_tile, ctx)
    writer.save_manifest()
    try:
        path = writer.pack_storage_path(db_path=db_path, existing=current.terrain_pack_path)
        apply_world_column(updated, "terrain_pack_path", path, ctx)
        apply_world_column(updated, "terrain_pack_hash", manifest.content_hash, ctx)
        await world_repository.update(updated)
    finally:
        # Files have changed even when validation/SQL save fails afterwards.
        if read_context is not None:
            for root in {old_root, writer.paths.root}:
                read_context.invalidate_pack_root(root)
    log_pack_finalize(
        world.world_uid,
        pack_path=updated.terrain_pack_path,
        content_hash=manifest.content_hash,
    )
    return updated
