"""L0 copies resolved bathymetry; no temporary floor synthesis (HY-12/6)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.coarseOpenWater import (
    apply_coarse_open_water,
)
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire
from tests.hydrology_fixtures import hydro_world


class TestLightSeaZ(unittest.TestCase):
    def _bake(self, floor_z, *, level=0, role=HydrologyCellRole.COASTAL_SEA, river=False):
        from tests.planning.consumers.test_l0_l2 import context
        from tests.planning.consumers.test_wiring import Composition, capture, world
        source = world(z_min=-100, z_max=40,
            world_map_cells_per_tile=4, hydrology={"enabled": True, "default_water_level": level,
                "default_lakes": {"autoresolve": False},
                "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
                "declared_basins": [{"location_uid": "water", "kind": "lake" if role is HydrologyCellRole.LAKE else "ocean",
                    "floor_z": floor_z if floor_z is not None else -12, "z_water_level": level,
                    "footprint": {"kind": "bbox", "x_min": 0, "x_max": 3000, "y_min": 0, "y_max": 3000}}]})
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        bundle = composition.prepare(capture(source))
        ctx = context(source, bundle, [(0, 0)])
        if floor_z is None:
            ctx.surface_bundle = None
        compose = LightGridCompose(ctx.scale)
        compose.ensure(0, 0, 0, 0).surface_z = 4
        if river:
            compose.ensure(0, 0, 0, 0).hydrology_role = WorldMapHydrologyRole.RIVER
        stats = apply_coarse_open_water(compose, ctx)
        return compose.get(0, 0, 0, 0), stats

    def test_sea_copies_resolved_floor(self):
        sea, stats = self._bake(-12)
        self.assertGreater(stats["z_applied"], 0)
        assert sea is not None
        self.assertEqual(sea.hydrology_role, WorldMapHydrologyRole.SEA)
        self.assertEqual(sea.surface_z, -12)

    def test_high_lake_uses_own_floor_above_ocean_default(self):
        lake, stats = self._bake(20, level=25, role=HydrologyCellRole.LAKE)
        self.assertEqual(lake.surface_z, 20)
        self.assertEqual(lake.hydrology_role, WorldMapHydrologyRole.LAKE)

    def test_missing_snapshot_is_an_explicit_contract_error(self):
        with self.assertRaisesRegex(ValueError, "frozen surface plan"):
            self._bake(None)

    def test_declared_river_height_survives_coarse_paint(self):
        river, stats = self._bake(-12, river=True)
        self.assertEqual(river.surface_z, 4)
        self.assertEqual(river.hydrology_role, WorldMapHydrologyRole.RIVER)
        self.assertEqual(stats["river_preserved"], 1)


if __name__ == "__main__":
    unittest.main()
