"""Unit tests — pack climate z ladder + volcanic local + elevation lapse."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climateAnchor import (
    AnchorSource,
    ClimateAnchorPoint,
)
from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
from app.application.worldData.pack.climate.climatePackSample import (
    resolve_pack_surface_z,
    sample_pack_climate_at,
)
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def _world(**overrides):
    base = dict(
        world_uid="w-climate-sample",
        map_cell_size_m=1000,
        elevation_lapse_rate=0.65,
        climate_temperature_peak_min=-40,
        climate_temperature_peak_max=50,
        climate_zone_registry=None,
        climate_local_influence_fraction=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestResolvePackSurfaceZ(unittest.TestCase):
    def test_ladder_prefers_l2_then_light_then_coarse(self) -> None:
        parent = ParentLightTile.from_cells(
            world_uid="w",
            gx=0,
            gy=0,
            side=2,
            tile_m=1000,
            cells=[
                WorldMapCellWire(tx=0, ty=0, surface_z=5),
                WorldMapCellWire(tx=1, ty=0, surface_z=5),
                WorldMapCellWire(tx=0, ty=1, surface_z=5),
                WorldMapCellWire(tx=1, ty=1, surface_z=5),
            ],
        )
        z = resolve_pack_surface_z(
            xm=0,
            ym=0,
            tile_m=1000,
            typical_elevation_z=1,
            coarse_surface_z={(0, 0): 3},
            parent_light=parent,
            l2_surface_z={(0, 0): 9},
        )
        self.assertEqual(z, 9)
        z2 = resolve_pack_surface_z(
            xm=0,
            ym=0,
            tile_m=1000,
            typical_elevation_z=1,
            coarse_surface_z={(0, 0): 3},
            parent_light=parent,
        )
        self.assertEqual(z2, 5)
        z3 = resolve_pack_surface_z(
            xm=0,
            ym=0,
            tile_m=1000,
            typical_elevation_z=1,
            coarse_surface_z={(0, 0): 3},
        )
        self.assertEqual(z3, 3)


class TestSamplePackClimateVolcanicHigh(unittest.TestCase):
    def test_high_z_cooler_than_low_with_same_volcanic_local(self) -> None:
        world = _world()
        pole = ClimatePoleField(poles=(), bbox=None)
        local = ClimateAnchorField(
            (
                ClimateAnchorPoint(
                    gx=0,
                    gy=0,
                    system_climate_zone="volcanic",
                    location_uid="volcano-1",
                    source=AnchorSource.MANUAL,
                ),
            ),
        )
        climate = MagicMock()
        climate.resolve_surface_sample.return_value = SimpleNamespace(
            system_climate_zone="volcanic",
            zone_location_uid="volcano-1",
            typical_elevation_z=2,
            base_temperature_override=35,
        )

        def _wae(_world, zone, z, base_temperature_override=None):
            base = base_temperature_override if base_temperature_override is not None else 35
            return round(base - 0.65 * (z / 100)), 5

        climate.weather_at_elevation.side_effect = _wae

        low = sample_pack_climate_at(
            world, pole, local,
            xm=0, ym=0, tile_m=1000,
            l2_surface_z={(0, 0): 0},
            climate=climate,
        )
        high = sample_pack_climate_at(
            world, pole, local,
            xm=0, ym=0, tile_m=1000,
            l2_surface_z={(0, 0): 2000},
            climate=climate,
        )
        self.assertLess(high.temperature_base, low.temperature_base)
        self.assertEqual(
            climate.resolve_surface_sample.call_args.kwargs.get("gx")
            or climate.resolve_surface_sample.call_args[0][4],
            0,
        )


class TestPackBakeDefaultsFinePolicy(unittest.TestCase):
    def test_defaults_spawn_player_and_full_none(self) -> None:
        from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults

        d = PackBakeDefaults.canonical_defaults()
        self.assertEqual(d.light_fine_tile_policy, "spawn_player")
        self.assertEqual(d.full_fine_tile_policy, "none")
        self.assertTrue(d.detailed_include_climate_fine)


if __name__ == "__main__":
    unittest.main()
