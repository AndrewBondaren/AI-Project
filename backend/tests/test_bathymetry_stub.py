"""Open-water bathymetry stub — mountain-rise analog (R5b / HY-BATH-1)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.application.worldData.generators.climate.climateAnchorField import ClimateAnchorField
from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField, GridBBox
from app.application.worldData.generators.hydrology.bathymetry import (
    ocean_stub_drop_amount,
    resolve_open_water_surface_z,
)
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
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.worldPack.hydrologyMaskWire import WorldMapHydrologyRole
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire


class TestStubElevationResolve(unittest.TestCase):
    def test_drop_from_pojo_fraction(self) -> None:
        policy = HydrologySeasPolicy(stub_drop_fraction_of_span=0.05)
        self.assertEqual(ocean_stub_drop_amount(policy, z_sea=0, z_min=-20), 1)
        self.assertEqual(
            resolve_open_water_surface_z(z_sea=0, z_min=-20, policy=policy),
            -1,
        )

    def test_prefers_coarse_carved_floor(self) -> None:
        policy = HydrologySeasPolicy(stub_drop_fraction_of_span=0.5)
        z = resolve_open_water_surface_z(
            z_sea=0, z_min=-100, policy=policy, coarse_z=-40,
        )
        self.assertEqual(z, -40)

    def test_stub_when_coarse_still_above_sea(self) -> None:
        policy = HydrologySeasPolicy(stub_drop_fraction_of_span=0.05)
        z = resolve_open_water_surface_z(
            z_sea=0, z_min=-20, policy=policy, coarse_z=5,
        )
        self.assertEqual(z, -1)


class TestLightSeaZ(unittest.TestCase):
    def test_sea_cells_below_plains_relief(self) -> None:
        world = SimpleNamespace(
            world_uid="world-bath-stub",
            z_min=-20,
            z_max=8,
            map_cell_size_m=1000,
            hydrology={
                "enabled": True,
                "default_seas": {"stub_drop_fraction_of_span": 0.05},
            },
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
                (0, 0): MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA),
            },
            sparse_meter_hydro={},
            meter_z_overrides={},
            coarse_relief_z={(0, 0): 4},
            # Simulate leaked land z on coarse (pre-fix) — stub must still drop.
            coarse_surface_z={(0, 0): 4},
        )
        scale = LightGridScale.from_tile(1000, 4)
        compose = LightGridCompose(scale=scale)
        # Plains-like relief base on a land cell outside sea paint path.
        compose.ensure(0, 0, 0, 0).surface_z = 4
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            surface_planning=surface,
        )
        stats = apply_coarse_open_water(compose, ctx)
        self.assertGreater(stats["z_applied"], 0)
        sea = compose.get(0, 0, 0, 0)
        assert sea is not None
        self.assertEqual(sea.hydrology_role, WorldMapHydrologyRole.SEA)
        self.assertLess(sea.surface_z, 4)
        self.assertEqual(sea.surface_z, -1)


if __name__ == "__main__":
    unittest.main()
