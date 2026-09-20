"""Pack climate row-batch pool vs serial fallback (CL-PAR)."""

from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import (
    ClimatePoleField,
    GridBBox,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import (
    ClimatePackBakeOrchestrator,
)
from app.dataModel.worldPack.climateFieldWire import ClimateSampleWire


def _world(**kwargs) -> SimpleNamespace:
    defaults = dict(
        world_uid="w-cl-par",
        fine_cells_per_map_cell=1000,
        world_map_cells_per_tile=8,
        climate_parallel_workers=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _surface_ctx(*, y_max: int = 7) -> MagicMock:
    bbox = GridBBox(x_min=0, x_max=1, y_min=0, y_max=y_max)
    ctx = MagicMock()
    ctx.coarse_hm.bbox = bbox
    ctx.pole_field = ClimatePoleField(poles=(), bbox=bbox)
    ctx.local_field = ClimateAnchorField(())
    ctx.coarse_surface_z = {}
    ctx.meter_z_overrides = {}
    return ctx


def _dummy_sample(*_args, **_kwargs) -> ClimateSampleWire:
    return ClimateSampleWire(temperature_base=1, rainfall=2)


class TestPackClimateParallel(unittest.IsolatedAsyncioTestCase):
    async def test_bake_coarse_uses_pool_when_workers_gt_one(self) -> None:
        orch = ClimatePackBakeOrchestrator()
        writer = MagicMock()
        writer.write_climate_coarse.return_value = "hash-coarse"
        mat_ctx = MaterializationContext(free_cores=4, parallel_workers_override=4)

        async def fake_map(items, compute):
            return [compute(item) for item in items]

        pool_instance = MagicMock()
        pool_instance.map_sync = AsyncMock(side_effect=fake_map)

        with patch(
            "app.application.worldData.pack.climate.climatePackBakeOrchestrator.ChunkComputePool",
            return_value=pool_instance,
        ) as pool_cls, patch(
            "app.application.worldData.pack.climate.climateCoarseBake.sample_pack_climate_at_macro",
            side_effect=_dummy_sample,
        ):
            result, n = await orch.bake_coarse(
                _world(), _surface_ctx(), writer, mat_ctx,
            )

        pool_cls.assert_called_once_with(
            4, thread_name_prefix="climate-compute", log_diagnostics=True,
        )
        pool_instance.map_sync.assert_awaited_once()
        pool_instance.shutdown.assert_called_once()
        self.assertEqual(n, 16)
        self.assertEqual(result.succeeded, 1)
        writer.write_climate_coarse.assert_called_once()

    async def test_bake_coarse_serial_when_workers_one(self) -> None:
        orch = ClimatePackBakeOrchestrator()
        writer = MagicMock()
        writer.write_climate_coarse.return_value = "hash-coarse"
        mat_ctx = MaterializationContext(free_cores=4, parallel_workers_override=1)

        with patch(
            "app.application.worldData.pack.climate.climatePackBakeOrchestrator.ChunkComputePool",
        ) as pool_cls, patch(
            "app.application.worldData.pack.climate.climateCoarseBake.sample_pack_climate_at_macro",
            side_effect=_dummy_sample,
        ):
            result, n = await orch.bake_coarse(
                _world(), _surface_ctx(), writer, mat_ctx,
            )

        pool_cls.assert_not_called()
        self.assertEqual(n, 16)
        self.assertEqual(result.succeeded, 1)

    async def test_climate_batch_logs_are_debug(self) -> None:
        orch = ClimatePackBakeOrchestrator()
        writer = MagicMock()
        writer.write_climate_coarse.return_value = "hash-coarse"
        mat_ctx = MaterializationContext(free_cores=1, parallel_workers_override=1)
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
        handler = _Capture()
        log.addHandler(handler)
        prev = log.level
        log.setLevel(logging.DEBUG)
        try:
            with patch(
                "app.application.worldData.pack.climate.climateCoarseBake.sample_pack_climate_at_macro",
                side_effect=_dummy_sample,
            ):
                await orch.bake_coarse(_world(), _surface_ctx(), writer, mat_ctx)
        finally:
            log.removeHandler(handler)
            log.setLevel(prev)

        starts = [
            r for r in records
            if "pack climate batch start" in r.getMessage()
        ]
        self.assertTrue(starts)
        self.assertTrue(all(r.levelno == logging.DEBUG for r in starts))
        self.assertIn("cpu=", starts[0].getMessage())
        self.assertIn("pool_workers=", starts[0].getMessage())
        self.assertIn("thread=", starts[0].getMessage())
        infos = [
            r for r in records
            if r.levelno == logging.INFO and "pack climate batch start" in r.getMessage()
        ]
        self.assertEqual(infos, [])


if __name__ == "__main__":
    unittest.main()
