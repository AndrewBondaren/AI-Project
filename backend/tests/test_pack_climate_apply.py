"""Unit tests: climate apply meter→macro, coarse/fine sample API, denser fine bake."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.pack.climatePackApply import apply_climate_to_view
from app.application.worldData.pack.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire, ClimateSampleWire
from app.dataModel.worldPack.mergeMapCells import MergedCellView


class TestClimateFieldSampleAt(unittest.TestCase):
    def test_coarse_macro_step_one(self) -> None:
        field = ClimateFieldWire(
            climate_status="coarse",
            origin_x=10,
            origin_y=20,
            width=2,
            height=2,
            sample_step_m=1,
            samples=[
                ClimateSampleWire(temperature_base=1, rainfall=10),
                ClimateSampleWire(temperature_base=2, rainfall=20),
                ClimateSampleWire(temperature_base=3, rainfall=30),
                ClimateSampleWire(temperature_base=4, rainfall=40),
            ],
        )
        self.assertEqual(field.sample_macro(10, 20).temperature_base, 1)
        self.assertEqual(field.sample_macro(11, 21).temperature_base, 4)
        self.assertIsNone(field.sample_macro(9, 20))
        with self.assertRaises(ValueError):
            field.sample_meters(10, 20)

    def test_fine_meter_step(self) -> None:
        field = ClimateFieldWire(
            climate_status="fine",
            origin_x=3000,
            origin_y=6000,
            width=2,
            height=1,
            sample_step_m=1500,
            samples=[
                ClimateSampleWire(temperature_base=11, rainfall=1),
                ClimateSampleWire(temperature_base=22, rainfall=2),
            ],
        )
        self.assertEqual(field.sample_meters(3000, 6000).temperature_base, 11)
        self.assertEqual(field.sample_meters(4499, 6000).temperature_base, 11)
        self.assertEqual(field.sample_meters(4500, 6000).temperature_base, 22)
        with self.assertRaises(ValueError):
            field.sample_macro(1, 1)

    def test_legacy_tier_a_maps_to_coarse(self) -> None:
        field = ClimateFieldWire.model_validate(
            {
                "tier": "A",
                "origin_x": 0,
                "origin_y": 0,
                "width": 1,
                "height": 1,
                "samples": [{"temperature_base": 1, "rainfall": 2}],
            },
        )
        self.assertEqual(field.climate_status, "coarse")


class TestApplyClimateMeterToMacro(unittest.TestCase):
    def test_apply_climate_converts_meters_to_macro(self) -> None:
        field = ClimateFieldWire(
            climate_status="coarse",
            origin_x=12,
            origin_y=12,
            width=1,
            height=1,
            samples=[ClimateSampleWire(temperature_base=17, rainfall=55)],
        )
        ctx = MagicMock()
        ctx.climate_tile_field.return_value = None
        ctx.climate_field.return_value = field
        world = SimpleNamespace(map_cell_size_m=3000, map_settings=None)
        view = MergedCellView(x=36000 + 100, y=36000 + 200, z=0)
        merged = apply_climate_to_view(ctx, world, view)
        self.assertEqual(merged.temperature_base, 17)
        self.assertEqual(merged.rainfall, 55)
        ctx.climate_field.assert_called_once()


class TestApplyClimatePreferFine(unittest.TestCase):
    def test_fine_wins_over_coarse(self) -> None:
        field_coarse = ClimateFieldWire(
            climate_status="coarse",
            origin_x=1,
            origin_y=1,
            width=1,
            height=1,
            samples=[ClimateSampleWire(temperature_base=1, rainfall=1)],
        )
        field_fine = ClimateFieldWire(
            climate_status="fine",
            origin_x=3000,
            origin_y=3000,
            width=1,
            height=1,
            sample_step_m=3000,
            samples=[ClimateSampleWire(temperature_base=99, rainfall=88)],
        )
        ctx = MagicMock()
        ctx.climate_tile_field.return_value = field_fine
        ctx.climate_field.return_value = field_coarse
        world = SimpleNamespace(map_cell_size_m=3000, map_settings=None)
        view = MergedCellView(x=3500, y=3500, z=0)
        merged = apply_climate_to_view(ctx, world, view)
        self.assertEqual(merged.temperature_base, 99)
        self.assertEqual(merged.rainfall, 88)
        ctx.climate_tile_field.assert_called_once()
        ctx.climate_field.assert_called()


class TestClimateCoarseRoundtrip(unittest.TestCase):
    def test_writer_reader_coarse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = WorldPackPaths.from_worlds_root(Path(tmp), "w-clim")
            paths.ensure_dirs()
            writer = WorldPackWriter(paths)
            field = ClimateFieldWire(
                climate_status="coarse",
                origin_x=0,
                origin_y=0,
                width=2,
                height=1,
                samples=[
                    ClimateSampleWire(temperature_base=5, rainfall=1),
                    ClimateSampleWire(temperature_base=6, rainfall=2),
                ],
            )
            writer.write_climate_coarse(field)
            from app.application.worldData.pack.worldPackReader import WorldPackReader

            restored = WorldPackReader(paths).read_climate_coarse()
            self.assertEqual(restored.width, 2)
            self.assertEqual(restored.samples[1].temperature_base, 6)
            self.assertEqual(restored.climate_status, "coarse")


if __name__ == "__main__":
    unittest.main()
