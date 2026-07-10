"""Pack loading progress snapshot — WP-15 / REVIEW-5."""

from __future__ import annotations

from app.application.worldData.loadingProgress import (
    LoadingProgressSnapshot,
    LocalGridLoading,
    WorldMapLoading,
)
from app.application.worldData.pack.packReadContext import PackReadContext
from app.db.models.world import World


class PackLoadingProgressFacade:
    def __init__(self, context: PackReadContext) -> None:
        self._ctx = context

    def get_loading_progress(self, world: World) -> LoadingProgressSnapshot:
        if not self._ctx.has_pack_for(world):
            return LoadingProgressSnapshot(world_uid=world.world_uid)
        manifest = self._ctx.reader_for(world).manifest
        world_map_ready = sum(1 for t in manifest.tiles if t.world_map_path)
        world_map_total = len(manifest.tiles) if manifest.tiles else world_map_ready
        loc_terrain = [loc.location_uid for loc in manifest.location_terrain_entries if loc.terrain_path]
        chunks_ready = manifest.wilderness_chunks_baked
        chunks_total = sum(len(t.chunks) for t in manifest.tiles) if manifest.tiles else chunks_ready
        return LoadingProgressSnapshot(
            world_uid=world.world_uid,
            world_map=WorldMapLoading(
                phase="background" if world_map_ready < world_map_total else "idle",
                world_map_tiles_ready=world_map_ready,
                world_map_tiles_total=world_map_total,
                location_terrain_ready=loc_terrain,
            ),
            local_grid=LocalGridLoading(
                phase="background" if chunks_ready < chunks_total else "idle",
                chunks_ready=chunks_ready,
                chunks_total=max(chunks_total, chunks_ready),
            ),
        )
