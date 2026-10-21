"""L0 copies resolved bathymetry; no temporary floor synthesis (HY-12/6)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
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
        world = hydro_world(
            world_uid="world-bath-stub",
            z_min=-20,
            z_max=8,
            fine_cells_per_map_cell=1000,
            hydrology={"enabled": True},
        )
        pole = MagicMock(spec=ClimatePoleField)
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 0},
        )
        surface = SurfaceTerrainContext(
            pole_field=pole,
            local_field=ClimateAnchorField(()),
            coarse_hm=hm,
            coarse_hydro={
                (0, 0): MapCellHydrology(role=role, z_water_level=level),
            },
            sparse_fine_hydro={},
            fine_z_overrides={},
            coarse_relief_z={(0, 0): 4},
            coarse_surface_z={} if floor_z is None else {(0, 0): floor_z},
        )
        scale = LightGridScale.from_tile(1000, 4)
        compose = LightGridCompose(scale=scale)
        # Plains-like relief base on a land cell outside sea paint path.
        compose.ensure(0, 0, 0, 0).surface_z = 4
        if river:
            compose.ensure(0, 0, 0, 0).hydrology_role = WorldMapHydrologyRole.RIVER
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            surface_planning=surface,
        )
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

    def test_missing_snapshot_does_not_invent_floor(self):
        sea, stats = self._bake(None)
        self.assertEqual(sea.surface_z, 4)
        self.assertEqual(stats["z_applied"], 0)

    def test_declared_river_height_survives_coarse_paint(self):
        river, stats = self._bake(-12, river=True)
        self.assertEqual(river.surface_z, 4)
        self.assertEqual(river.hydrology_role, WorldMapHydrologyRole.RIVER)
        self.assertEqual(stats["river_preserved"], 1)


if __name__ == "__main__":
    unittest.main()
