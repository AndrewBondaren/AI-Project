"""Pack fine-terrain refine parallel policy — pool path vs serial fallback."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.worldData.pack.refine.fineTerrainRefineOrchestrator import FineTerrainRefineOrchestrator
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.materializationContext import MaterializationContext
from app.db.models.mapCell import MapCell


def _world() -> SimpleNamespace:
    return SimpleNamespace(
        world_uid="w-par",
        map_cell_size_m=3000,
        terrain_chunk_columns=32,
        terrain_parallel_workers=None,
    )


def _plains_cell() -> MapCell:
    return MapCell(world_uid="w-par", x=0, y=0, z=0, system_terrain="plains")


class TestFineTerrainRefineParallel(unittest.IsolatedAsyncioTestCase):

    def _setup(self) -> tuple[MagicMock, MagicMock, list[ColumnRect], MaterializationContext]:
        terrain = MagicMock()
        terrain.build_tile_surface_state.return_value = MagicMock()
        terrain.generate_chunk_cells_sync.return_value = [_plains_cell()]

        writer = MagicMock()
        writer.write_wilderness_chunk.return_value = "hash"
        writer.manifest = MagicMock()

        rects = [
            ColumnRect(x_min=0, x_max=31, y_min=0, y_max=31),
            ColumnRect(x_min=32, x_max=63, y_min=0, y_max=31),
            ColumnRect(x_min=64, x_max=95, y_min=0, y_max=31),
            ColumnRect(x_min=96, x_max=127, y_min=0, y_max=31),
        ]
        mat_ctx = MaterializationContext(free_cores=4, parallel_workers_override=4)
        return terrain, writer, rects, mat_ctx

    async def test_refine_rects_uses_chunk_compute_pool_when_workers_gt_one(self) -> None:
        terrain, writer, rects, mat_ctx = self._setup()
        l2 = FineTerrainRefineOrchestrator(terrain)

        async def fake_pool(items, compute, on_result):
            for item in items:
                result = compute(item)
                await on_result(item, result)

        pool_instance = MagicMock()
        pool_instance.map_sync_with_callback = AsyncMock(side_effect=fake_pool)

        with patch(
            "app.application.worldData.pack.refine.fineTerrainRefineOrchestrator.ChunkComputePool",
            return_value=pool_instance,
        ) as pool_cls:
            result, written, total = await l2._refine_rects(
                _world(),
                [],
                writer,
                mat_ctx,
                surface_ctx=MagicMock(),
                tile_gx=0,
                tile_gy=0,
                rects=rects,
                volumes=[],
                refine_role="scene",
                phase="scene",
            )

        pool_cls.assert_called_once_with(
            4, thread_name_prefix="pack-compute", log_diagnostics=True,
        )
        pool_instance.shutdown.assert_called_once()
        pool_instance.map_sync_with_callback.assert_awaited_once()
        self.assertEqual(total, 4)
        self.assertEqual(written, 4)
        self.assertEqual(result.succeeded, 4)
        self.assertEqual(terrain.generate_chunk_cells_sync.call_count, 4)

    async def test_refine_rects_serial_when_single_chunk(self) -> None:
        terrain, writer, rects, mat_ctx = self._setup()
        l2 = FineTerrainRefineOrchestrator(terrain)

        with patch(
            "app.application.worldData.pack.refine.fineTerrainRefineOrchestrator.ChunkComputePool",
        ) as pool_cls:
            result, written, total = await l2._refine_rects(
                _world(),
                [],
                writer,
                mat_ctx,
                surface_ctx=MagicMock(),
                tile_gx=0,
                tile_gy=0,
                rects=rects[:1],
                volumes=[],
                refine_role="scene",
                phase="scene",
            )

        pool_cls.assert_not_called()
        self.assertEqual(total, 1)
        self.assertEqual(written, 1)
        self.assertEqual(result.succeeded, 1)


if __name__ == "__main__":
    unittest.main()
