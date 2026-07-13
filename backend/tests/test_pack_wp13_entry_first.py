"""WP-13 / WP-PERF-10 — background enqueue is ring-capped, not whole tile."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.pack.refine.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.fineTerrainRefineOrchestrator import (
    FineTerrainRefineOrchestrator,
)
from app.application.worldData.generators.coordinates.worldTile import (
    iter_meter_chunks,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.worldMapSettings import terrain_chunk_columns
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy


def _world(*, cell_m: int = 1000, chunk: int = 32) -> SimpleNamespace:
    return SimpleNamespace(
        world_uid="w-wp13",
        map_cell_size_m=cell_m,
        terrain_chunk_columns=chunk,
        terrain_parallel_workers=None,
    )


class TestScheduleTileBackgroundRings(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_capped_by_background_expand_radius(self) -> None:
        world = _world()
        orch = FineTerrainRefineOrchestrator(MagicMock())
        queue = ChunkRefineQueue(max_workers=1)
        policy = SceneVolumePolicy.canonical_defaults()
        cell_m = world.map_cell_size_m
        chunk_size = terrain_chunk_columns(world)
        meter_bbox = meter_bbox_for_tile(0, 0, cell_m)
        full_tile = sum(1 for _ in iter_meter_chunks(meter_bbox, chunk_size))

        # Anchor near tile center so ring is interior.
        ax = cell_m // 2
        ay = cell_m // 2
        enqueued = await orch.schedule_tile_background(
            world, queue, ax, ay, 0, 0,
        )
        self.assertGreater(enqueued, 0)
        self.assertLess(enqueued, full_tile)
        # Whole-tile enqueue was ~900+ jobs at 1000m/32; rings must stay far below.
        self.assertLess(enqueued, full_tile // 4)
        self.assertEqual(enqueued, len(queue))
        self.assertEqual(policy.background_expand_radius_m, 60)

    async def test_skip_scene_rects_excludes_scene_chunks(self) -> None:
        world = _world()
        orch = FineTerrainRefineOrchestrator(MagicMock())
        queue = ChunkRefineQueue(max_workers=1)
        ax, ay = 500, 500
        skip = orch.scene_chunk_indices(world, 0, 0, ax, ay)
        self.assertGreater(len(skip), 0)
        enqueued = await orch.schedule_tile_background(
            world, queue, ax, ay, 0, 0,
            skip_scene_rects=skip,
        )
        pending = {(gx, gy, cx, cy) for gx, gy, cx, cy, _ in queue.pending_items()}
        for cx, cy in skip:
            self.assertNotIn((0, 0, cx, cy), pending)
        self.assertEqual(enqueued, len(pending))


if __name__ == "__main__":
    unittest.main()
