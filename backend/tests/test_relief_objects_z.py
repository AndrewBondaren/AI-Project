"""Pass 1.4 relief objects z + grid hydro detect thresholds."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.application.worldData.generators.climate.anchorDetect import (
    ProminenceScale,
    detect_terrain_features,
    grid_prominence_thresholds,
    prominence_thresholds_for_surface_z,
)
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.reliefObjects import (
    apply_relief_objects_z,
    mountain_rise_amount,
    resolve_mountain_surface_z,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import (
    _river_source_min_z,
)
from app.application.worldData.generators.hydrology.types import RiverTypeClassify
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.contributors.mountain import MountainContributor
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexWire
from app.db.models.mapCell import MapCell


def _world(**overrides):
    base = dict(
        world_uid="world-relief-test",
        map_cell_size_m=1000,
        world_map_cells_per_tile=None,
        z_min=0,
        z_max=8,
        map_subsurface_depth=0,
        terrain_masks={},
        terrain_registry=[
            {"system_terrain": "plains", "display_name": "Plains"},
            {"system_terrain": "mountain", "display_name": "Mountain"},
            {"system_terrain": "ravine", "display_name": "Ravine"},
            {"system_terrain": "forest", "display_name": "Forest"},
            {"system_terrain": "road", "display_name": "Road"},
        ],
        climate_zone_registry=None,
        hydrology={"enabled": False},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestElevationResolve(unittest.TestCase):
    def test_rise_from_pojo_fraction(self) -> None:
        policy = WorldTerrainMasks.canonical_defaults().default_mountains
        self.assertEqual(policy.rise_fraction_of_z_max, 0.25)
        self.assertEqual(mountain_rise_amount(policy, 8), 2)
        self.assertEqual(
            resolve_mountain_surface_z(3, z_min=0, z_max=8, policy=policy),
            5,
        )
        self.assertEqual(
            resolve_mountain_surface_z(7, z_min=0, z_max=8, policy=policy),
            8,
        )


class TestApplyReliefObjectsZ(unittest.TestCase):
    def test_raises_some_cells_and_clamps(self) -> None:
        world = _world()
        # Force autoresolve on: lower threshold so flat z=1 still scores via ridge noise sometimes.
        world.terrain_masks = {
            "default_mountains": {
                "threshold": 0.0,
                "rise_fraction_of_z_max": 0.25,
            },
        }
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 2, 0, 2),
            surface_z={(x, y): 1 for x in range(3) for y in range(3)},
        )
        apply_relief_objects_z(world, [], hm)
        zs = list(hm.surface_z.values())
        self.assertTrue(any(z > 1 for z in zs), zs)
        self.assertTrue(all(z <= 8 for z in zs), zs)
        self.assertEqual(max(zs), 3)  # 1 + round(8*0.25)=1+2


class TestGridDetectThresholds(unittest.TestCase):
    def test_scaled_thresholds_find_peak_and_basin(self) -> None:
        # Local peak at (1,1)=3, basin at (1,1)=0 on small span.
        peak_cells = [
            MapCell(world_uid="w", x=x, y=y, z=0, system_terrain="plains")
            for x in range(3)
            for y in range(3)
        ]
        for c in peak_cells:
            if c.x == 1 and c.y == 1:
                c.z = 3
        thr = grid_prominence_thresholds(3)
        peaks = detect_terrain_features(
            peak_cells,
            scale=ProminenceScale.GRID,
            thresholds=thr,
        )
        self.assertTrue(any(f.kind == "peak" for f in peaks))

        basin_cells = [
            MapCell(world_uid="w", x=x, y=y, z=3, system_terrain="plains")
            for x in range(3)
            for y in range(3)
        ]
        for c in basin_cells:
            if c.x == 1 and c.y == 1:
                c.z = 0
        basins = detect_terrain_features(
            basin_cells,
            scale=ProminenceScale.GRID,
            thresholds=thr,
        )
        self.assertTrue(any(f.kind == "basin" for f in basins))

    def test_metric_defaults_unchanged(self) -> None:
        thr = prominence_thresholds_for_surface_z(
            {(0, 0): 0, (1, 0): 3}, scale=ProminenceScale.METRIC,
        )
        self.assertEqual(thr.peak, 50)
        self.assertEqual(thr.basin, 25)

    def test_river_source_min_z_scales_to_land(self) -> None:
        hm = SurfaceHeightmap(
            world_uid="w",
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 7},
        )
        tc = RiverTypeClassify(
            mountain_min_source_z=40,
            path_mountain_fraction=0.5,
            rapid_drop_threshold_m=5,
            mountain_bed_steepness_factor=1.0,
            foothill_gradient_threshold=0.1,
        )
        # configured=20, scaled=ceil(7/2)=4 → min=4
        self.assertEqual(_river_source_min_z(hm, tc), 4)


class TestPrepareSurfaceOrder(unittest.TestCase):
    def test_relief_objects_called_before_hydro(self) -> None:
        from app.application.worldData.generators.terrain.passes import surfaceTerrainContext as mod

        world = _world()
        locations: list = []
        order: list[str] = []

        coarse = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 1},
        )

        def fake_relief(*_a, **_k):
            order.append("relief")
            return coarse

        hydro = MagicMock()
        hydro.apply.side_effect = lambda *_a, **_k: (
            order.append("hydro"),
            SimpleNamespace(cell_index=SimpleNamespace(by_cell={})),
        )[1]

        with (
            patch.object(mod, "run_pole_resolve_pass", return_value=MagicMock()),
            patch.object(mod, "run_surface_pass_coarse", return_value=coarse),
            patch.object(mod, "apply_relief_objects_z", side_effect=fake_relief),
            patch.object(mod, "is_hydrology_enabled", return_value=True),
            patch.object(mod, "apply_declared_meter_river_carves", return_value=({}, {})),
            patch.object(mod, "build_local_field_from_coarse", return_value=MagicMock()),
        ):
            ctx = mod.prepare_surface_terrain_context(
                world, locations, hydrology_generator=hydro,
            )
        self.assertIsNotNone(ctx)
        self.assertEqual(order, ["relief", "hydro"])
        assert ctx is not None
        self.assertEqual(ctx.coarse_relief_z, {(0, 0): 1})


class TestAntiDoubleRise(unittest.TestCase):
    def test_light_relief_uses_pre14_not_post14(self) -> None:
        """Relief base is coarse_relief_z; mountain then applies one rise (not 2×)."""
        from app.application.worldData.generators.climate.climateAnchorField import (
            ClimateAnchorField,
        )
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            SurfaceTerrainContext,
        )
        from app.application.worldData.generators.terrain.reliefObjects import (
            mountain_rise_amount,
        )
        from app.application.worldData.pack.bake.lightGrid.contributors.relief import (
            ReliefContributor,
        )

        world = _world(z_max=8, z_min=0, map_cell_size_m=1000)
        policy = WorldTerrainMasks.canonical_defaults().default_mountains
        rise = mountain_rise_amount(policy, 8)
        self.assertEqual(rise, 2)

        pole = MagicMock()
        pole.sample.return_value = SimpleNamespace(
            typical_elevation_z=1,
            system_climate_zone="temperate",
        )
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 1 + rise},
        )
        surface = SurfaceTerrainContext(
            pole_field=pole,
            local_field=ClimateAnchorField(()),
            coarse_hm=hm,
            coarse_hydro={},
            sparse_meter_hydro={},
            meter_z_overrides={},
            coarse_relief_z={(0, 0): 1},
            coarse_surface_z={(0, 0): 1 + rise},
        )
        scale = LightGridScale.from_tile(1000, 4)
        compose = LightGridCompose(scale=scale)
        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            surface_planning=surface,
            pole_field=pole,
        )
        ReliefContributor().apply(compose, ctx)
        relief_z = compose.get(0, 0, 0, 0).surface_z
        # Base from pre-1.4 (=1) ± noise amplitude 1 → in [0, 2], not post-1.4 (=3).
        self.assertLessEqual(relief_z, 1 + 1)
        self.assertNotEqual(relief_z, 1 + rise)

        world.terrain_masks = {
            "default_mountains": {
                "autoresolve": True,
                "threshold": 0.0,
                "rise_fraction_of_z_max": 0.25,
                "declare_radius_light": 0,
            },
        }
        cell = compose.get(0, 0, 0, 0)
        assert cell is not None
        cell.climate_zone_id = ClimateZone.TEMPERATE.world_map_wire_id()
        before = cell.surface_z
        MountainContributor().apply(compose, ctx)
        after = compose.get(0, 0, 0, 0).surface_z
        self.assertEqual(after, min(8, before + rise))


class TestMountainLightZ(unittest.TestCase):
    def test_paint_mountain_raises_surface_z(self) -> None:
        world = _world(z_max=8, z_min=0)
        world.terrain_masks = {
            "default_mountains": {
                "autoresolve": True,
                "threshold": 0.0,
                "rise_fraction_of_z_max": 0.25,
                "declare_radius_light": 0,
            },
        }
        scale = LightGridScale.from_tile(1000, 4)
        compose = LightGridCompose(scale=scale)
        cell = compose.ensure(0, 0, 0, 0)
        cell.surface_z = 2
        cell.climate_zone_id = ClimateZone.TEMPERATE.world_map_wire_id()
        base_z = cell.surface_z

        ctx = LightGridBakeContext(
            world=world,
            locations=[],
            locations_index=LocationsIndexWire(locations=[]),
            tiles=[(0, 0)],
            scale=scale,
            surface_planning=None,
            nodes=[],
            edges=[],
        )
        MountainContributor().apply(compose, ctx)
        self.assertEqual(compose.get(0, 0, 0, 0).system_terrain, "mountain")
        self.assertGreater(compose.get(0, 0, 0, 0).surface_z, base_z)


class TestMutateContract(unittest.TestCase):
    def test_apply_relief_mutates_in_place(self) -> None:
        world = _world(z_max=8, z_min=0)
        world.terrain_masks = {
            "default_mountains": {"threshold": 0.0, "rise_fraction_of_z_max": 0.25},
        }
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 1, 0, 1),
            surface_z={(0, 0): 1, (1, 0): 1, (0, 1): 1, (1, 1): 1},
        )
        pole = MagicMock()
        pole.sample.return_value = SimpleNamespace(typical_elevation_z=0)
        out = apply_relief_objects_z(world, [], hm, pole_field=pole, light_side=32)
        self.assertIs(out, hm)
        self.assertTrue(any(z > 1 for z in hm.surface_z.values()))

    def test_apply_mountain_requires_pole(self) -> None:
        from app.application.worldData.generators.terrain.reliefObjects.mountainZ import (
            apply_mountain_z,
        )

        world = _world()
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={(0, 0): 1},
        )
        with self.assertRaises(TypeError):
            apply_mountain_z(world, [], hm, light_side=32)  # type: ignore[call-arg]


class TestTerrainMasksKnobs(unittest.TestCase):
    def test_pojo_knobs_present(self) -> None:
        masks = WorldTerrainMasks.canonical_defaults()
        self.assertEqual(masks.default_mountains.rise_fraction_of_z_max, 0.25)
        self.assertEqual(masks.default_ravines.drop_z, 1)


if __name__ == "__main__":
    unittest.main()
