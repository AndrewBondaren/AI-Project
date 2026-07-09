"""Materialization parallel infra — policy, pool, climate pass-through."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.chunkComputePool import ChunkComputePool, split_contiguous_batches
from app.application.worldData.generators.assemblers.climateAssembler.passes.cellWeatherPass import (
    run_cell_weather_pass,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    resolve_insert_only,
    resolve_materialization_context,
)
from app.application.worldData.parallelPolicy import (
    resolve_climate_workers,
    resolve_terrain_workers,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation


def _world(**kwargs):
    defaults = {
        "world_uid": "w-par",
        "terrain_parallel_workers": None,
        "climate_parallel_workers": None,
        "default_climate_zone": "temperate",
        "climate_pole_mode": "autoresolve",
        "climate_pole_preset": "binary",
        "elevation_lapse_rate": 0.65,
        "climate_zone_registry": {"temperate": {}},
        "terrain_registry": [{"system_key": "plains"}],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestParallelPolicy(unittest.TestCase):

    def test_resolve_terrain_workers_free_cores(self):
        world = _world()
        ctx = MaterializationContext(free_cores=5)
        self.assertEqual(resolve_terrain_workers(ctx, world), 5)

    def test_resolve_terrain_workers_override(self):
        world = _world()
        ctx = MaterializationContext(free_cores=8, parallel_workers_override=3)
        self.assertEqual(resolve_terrain_workers(ctx, world), 3)

    def test_resolve_terrain_workers_world_cap(self):
        world = _world(terrain_parallel_workers=2)
        ctx = MaterializationContext(free_cores=5)
        self.assertEqual(resolve_terrain_workers(ctx, world), 2)

    def test_resolve_climate_workers_world_cap(self):
        world = _world(climate_parallel_workers=4)
        ctx = MaterializationContext(free_cores=8)
        self.assertEqual(resolve_climate_workers(ctx, world), 4)

    def test_debug_stub_free_cores(self):
        world = _world()
        ctx = resolve_materialization_context(world)
        self.assertEqual(ctx.free_cores, 5)

    def test_chunks_per_commit_default(self):
        world = _world()
        ctx = resolve_materialization_context(world)
        self.assertEqual(ctx.chunks_per_commit, 8)

    def test_insert_only_auto_detect_empty(self):
        ctx = MaterializationContext(free_cores=5)
        resolved = resolve_insert_only(ctx, world_has_cells=False)
        self.assertTrue(resolved.insert_only)

    def test_insert_only_auto_detect_nonempty(self):
        ctx = MaterializationContext(free_cores=5)
        resolved = resolve_insert_only(ctx, world_has_cells=True)
        self.assertFalse(resolved.insert_only)

    def test_insert_only_explicit_override(self):
        ctx = MaterializationContext(free_cores=5, insert_only=True)
        resolved = resolve_insert_only(ctx, world_has_cells=True)
        self.assertTrue(resolved.insert_only)


class TestChunkComputePool(unittest.IsolatedAsyncioTestCase):

    async def test_map_sync_serial_workers(self):
        pool = ChunkComputePool(1)
        items = [1, 2, 3]
        out = await pool.map_sync(items, lambda x: x * 2)
        self.assertEqual(out, [2, 4, 6])

    async def test_map_sync_parallel_preserves_order(self):
        pool = ChunkComputePool(3)

        def slow_square(x: int) -> int:
            return x * x

        out = await pool.map_sync([1, 2, 3, 4], slow_square)
        self.assertEqual(out, [1, 4, 9, 16])

    async def test_map_sync_with_callback_serial_persist(self):
        pool = ChunkComputePool(2)
        persisted: list[int] = []

        async def on_result(_item: int, value: int) -> None:
            persisted.append(value)

        out = await pool.map_sync_with_callback([1, 2], lambda x: x + 10, on_result)
        self.assertEqual(out, [11, 12])
        self.assertEqual(persisted, [11, 12])


class TestSplitBatches(unittest.TestCase):

    def test_contiguous_batches(self):
        batches = split_contiguous_batches([1, 2, 3, 4, 5], 2)
        self.assertEqual(batches, [[1, 2, 3], [4, 5]])


class TestCellWeatherPassThrough(unittest.TestCase):

    def test_hydrology_preserved(self):
        world = _world()
        loc = NamedLocation(
            world_uid="w-par",
            location_uid="loc-1",
            display_name="anchor",
            system_location_type="climate_anchor",
            created_at="2026-01-01T00:00:00Z",
            map_x=0,
            map_y=0,
            map_z=0,
            is_mobile=False,
            system_climate_zone="temperate",
        )
        cell = MapCell(
            world_uid="w-par",
            x=0,
            y=0,
            z=10,
            system_terrain="plains",
            hydrology={"liquid_candidate": True, "role": "river_bed"},
        )
        pole_field = MagicMock()
        pole_field.is_empty.return_value = True
        anchor_field = MagicMock()
        anchor_field.anchors = []

        from app.application.worldData.generators.climate.climateGeneratorService import (
            ClimateGeneratorService,
        )
        svc = ClimateGeneratorService()
        # Monkeypatch resolve to avoid full climate stack
        svc.resolve_surface_sample = MagicMock(return_value=SimpleNamespace(
            system_climate_zone="temperate",
            base_temperature_override=None,
            zone_location_uid="loc-1",
        ))
        svc.weather_at_elevation = MagicMock(return_value=(15, 100))

        result = run_cell_weather_pass(
            world, [loc], pole_field, anchor_field, [cell], svc,
        )
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0].hydrology)
        self.assertTrue(result[0].hydrology.get("liquid_candidate"))


if __name__ == "__main__":
    unittest.main()
