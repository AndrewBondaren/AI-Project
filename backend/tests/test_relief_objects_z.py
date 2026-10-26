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
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.contributors.mountain import MountainContributor
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire
from app.db.models.mapCell import MapCell


def _world(**overrides):
    base = dict(
        world_uid="world-relief-test",
        fine_cells_per_map_cell=1000,
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
    def test_rise_from_kind_profile(self) -> None:
        from app.dataModel.terrainMasks.mountain import MountainKind

        self.assertEqual(mountain_rise_amount(MountainKind.ROCKY, 8), 3)
        self.assertEqual(
            resolve_mountain_surface_z(3, z_min=0, z_max=8, kind=MountainKind.ROCKY),
            6,
        )
        self.assertEqual(
            resolve_mountain_surface_z(7, z_min=0, z_max=8, kind=MountainKind.ROCKY),
            8,
        )


class TestApplyReliefObjectsZ(unittest.TestCase):
    def test_raises_some_cells_and_clamps(self) -> None:
        world = _world()
        # Force autoresolve on: lower threshold so flat z=1 still scores via ridge noise sometimes.
        world.terrain_masks = {
            "default_mountains": {
                "threshold": 0.0,
            },
        }
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 2, 0, 2),
            surface_z={(x, y): 1 for x in range(3) for y in range(3)},
        )
        pole = MagicMock()
        pole.sample.return_value = SimpleNamespace(typical_elevation_z=0)
        apply_relief_objects_z(world, [], hm, pole_field=pole, light_side=32)
        zs = list(hm.surface_z.values())
        self.assertTrue(any(z > 1 for z in zs), zs)
        self.assertTrue(all(z <= 8 for z in zs), zs)
        # ROCKY rise = round(8*0.35)=3; SideFill may yield <1 fraction → max 3 or 4
        self.assertGreaterEqual(max(zs), 3)
        self.assertLessEqual(max(zs), 4)


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
        from tests.planning.consumers.test_wiring import world, planning_kwargs, capture
        from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
        deps = planning_kwargs(self)
        composition = self._surface_composition
        source = world()
        with patch.object(composition.registry, "build", wraps=composition.registry.build) as builds:
            _, working = SurfacePlanningEntry(deps["planning"], deps["capture"]).require_plan_inputs(source, [], wait=deps["wait"])
        phases = [str(call.args[0].metadata.id) for call in builds.call_args_list]
        self.assertLess(phases.index("surface.pc.relief"), phases.index("surface.pc.hydrology_routes"))
        terrain = composition.prepare(capture(source))
        self.assertEqual(working.terrain.relief_z, {(cell.gx, cell.gy): z for cell, z in terrain.terrain_base.payload.surface_z})


class TestAntiDoubleRise(unittest.TestCase):
    def test_light_base_is_frozen_pre_mountain_and_never_double_rises(self) -> None:
        from tests.planning.consumers.test_l0_l2 import mountain_source, context
        from tests.planning.consumers.test_wiring import Composition, capture
        from app.application.worldData.pack.bake.lightGrid.contributors.relief import ReliefContributor
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        source = mountain_source()
        bundle = composition.prepare(capture(source))
        ctx = context(source, bundle)
        compose = LightGridCompose(ctx.scale)
        ReliefContributor().apply(compose, ctx)
        for ref, z in bundle.relief.payload.light.base_surface_z:
            self.assertEqual(compose.get(ref.gx, ref.gy, ref.tx, ref.ty).surface_z, z)
        MountainContributor().apply(compose, ctx)
        first = [compose.to_wire_tile(*tile) for tile in ctx.tiles]
        MountainContributor().apply(compose, ctx)
        self.assertEqual(first, [compose.to_wire_tile(*tile) for tile in ctx.tiles])


class TestMountainLightZ(unittest.TestCase):
    def test_paint_mountain_uses_frozen_absolute_surface_z(self) -> None:
        from tests.planning.consumers.test_l0_l2 import mountain_source, context
        from tests.planning.consumers.test_wiring import Composition, capture
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        source = mountain_source()
        bundle = composition.prepare(capture(source))
        ctx = context(source, bundle)
        compose = LightGridCompose(ctx.scale)
        MountainContributor().apply(compose, ctx)
        self.assertTrue(bundle.relief.payload.light.mountain_cells)
        for effect in bundle.relief.payload.light.mountain_cells:
            ref = effect.cell
            self.assertEqual(compose.get(ref.gx, ref.gy, ref.tx, ref.ty).surface_z, effect.surface_z)


class TestMutateContract(unittest.TestCase):
    def test_apply_relief_mutates_in_place(self) -> None:
        world = _world(z_max=8, z_min=0)
        world.terrain_masks = {
            "default_mountains": {"threshold": 0.0},
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
        from app.dataModel.terrainMasks.mountain import MountainKind, mountain_kind_profile

        masks = WorldTerrainMasks.canonical_defaults()
        self.assertEqual(masks.default_mountains.default_radius_m, 500)
        self.assertEqual(masks.default_mountains.default_kind, MountainKind.ROCKY)
        self.assertEqual(masks.default_mountains.sides, ())
        sides = masks.default_mountains.resolved_sides()
        self.assertEqual(len(sides), 6)
        self.assertEqual(mountain_kind_profile(MountainKind.ROCKY).rise_fraction_of_z_max, 0.35)
        self.assertEqual(masks.default_ravines.drop_z, 1)
        self.assertEqual(masks.declared_mountains, [])

    def test_policy_sides_length_mismatch_raises(self) -> None:
        from app.dataModel.terrainMasks.mountain import MountainSideSpec
        from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy

        policy = MountainsCategoryPolicy(
            sides=[MountainSideSpec(), MountainSideSpec()],
        )
        with self.assertRaises(ValueError):
            policy.resolved_sides()


if __name__ == "__main__":
    unittest.main()
