from copy import replace
from unittest import TestCase

from app.application.worldData.generators.hydrology.water.levelFill import level_fill
from app.application.worldData.generators.terrain.passes.lightSurfaceRefine import refine_light_surface
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.floorProfile import BasinFloorEvaluator
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile, FieldFloorProfile
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.terrain_base.fixtures import inputs, prepare


class PreWaterTerrainTests(TestCase):
    def test_natural_relief_hills_then_accepted_floor_then_fill(self):
        values = inputs()
        surface, protected = prepare(values)
        natural, same_protected = prepare(inputs(hills=False))
        self.assertEqual(protected, same_protected)
        self.assertTrue(protected)
        self.assertIn((8, 8), protected)
        self.assertNotIn((5, 5), protected)  # Outside the diamond, inside its light-cell projection.
        raised = {cell for cell in surface.surface_z if surface.surface_z[cell] > natural.surface_z[cell]}
        self.assertTrue(raised)
        self.assertFalse(raised & protected)
        self.assertTrue(any(surface.surface_z[cell] > 0 for cell in protected))
        before = dict(surface.surface_z)
        topology = fine_topology(values[2].topology, values[0].grid.fine_span)
        profile = SampledFloorProfile(space=CoordinateSpace.WORLD_FINE_GRID,
            samples=tuple((cell, -5) for cell in sorted(before, key=lambda c: (c[1], c[0]))))
        basin = BasinSpec(source_uid="accepted", kind=BasinKind.LAKE, liquid="water",
            footprint=frozenset(before), z_water_level=0, floor_z=-5,
            bands=HydrologyBands(min=1, max=2), floor_profile=profile)
        written = apply_basin_z(surface, (basin,), topology, reserved=protected,
                               coordinate_space=CoordinateSpace.WORLD_FINE_GRID)
        self.assertEqual(written, len(before) - len(protected))
        self.assertTrue(all(surface.surface_z[cell] == -5 for cell in before.keys() - protected))
        self.assertTrue(all(surface.surface_z[cell] == before[cell] for cell in protected))
        fill = level_fill(surface.surface_z, ((0, 0),), 0, topology)
        self.assertEqual(fill.cells, frozenset(cell for cell, z in surface.surface_z.items() if z < 0))
        self.assertTrue(raised <= fill.cells)
        self.assertFalse({cell for cell in protected if before[cell] >= 0} & fill.cells)
        self.assertEqual(basin.floor_profile, profile)

    def test_field_floor_uses_accepted_recipe_and_same_natural_base(self):
        values = inputs(mountain=False)
        surface, protected = prepare(values)
        topology = fine_topology(values[2].topology, values[0].grid.fine_span)
        profile = FieldFloorProfile(recipe=NoiseRecipe(seed_root="accepted-recipe", topology=topology,
            noise_policy=ContinentalNoisePolicy()), level=0, depth=6, z_min=-20)
        basin = BasinSpec(source_uid="field", kind=BasinKind.SEA, liquid="water", footprint=frozenset(surface.surface_z),
            z_water_level=0, floor_z=-6, bands=HydrologyBands(min=1, max=2), floor_profile=profile)
        evaluator = BasinFloorEvaluator(profile, topology=topology, coordinate_space=CoordinateSpace.WORLD_FINE_GRID, grid=None)
        apply_basin_z(surface, (basin,), topology, reserved=protected, coordinate_space=CoordinateSpace.WORLD_FINE_GRID)
        self.assertEqual(surface.surface_z, {cell: evaluator.sample(cell) for cell in surface.surface_z})
        self.assertEqual(level_fill(surface.surface_z, ((0, 0),), 0, topology).cells, basin.footprint)

    def test_partial_queries_match_full_heights_and_protection(self):
        for mode in (WorldTopologyMode.PLANAR, WorldTopologyMode.WRAPPED, WorldTopologyMode.SPHERE):
            with self.subTest(mode=mode):
                values = list(inputs())
                values[2] = replace(values[2], topology=replace(values[2].topology, mode=mode))
                full, protected = prepare(values)
                stitched, reservations = {}, set()
                for window in (coverage(7, 25, 0, 32), coverage(25, 32, 0, 32), coverage(0, 7, 0, 32)):
                    part, kept = prepare(values, window)
                    stitched.update(part.surface_z)
                    reservations.update(kept)
                self.assertEqual(stitched, full.surface_z)
                self.assertEqual(reservations, protected)
                self.assertEqual(prepare(values)[0], full)

    def test_capture_mismatch_and_out_of_world_scope_rejected(self):
        base, relief, support, climate, terrain = inputs()
        for invalid in ((replace(base, seed=99), relief, support, climate, terrain),
                        (base, replace(relief, z_max=50), support, climate, terrain),
                        (base, relief, replace(support, grid=SurfaceGridSettings(fine_span=8, light_side=4)), climate, terrain),
                        (base, relief, support, climate, replace(terrain, dependencies=()))):
            with self.subTest(invalid=invalid[0]), self.assertRaises(ValueError):
                prepare(invalid)
        with self.assertRaisesRegex(ValueError, "canonical"):
            prepare(cells=coverage(-1, 1))

    def test_cancellation_propagates(self):
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            prepare(control=Stop())

    def test_clipped_fill_cannot_silently_hide_unknown_rim(self):
        values = inputs(mountain=False)
        surface, _ = prepare(values, coverage(0, 1, 0, 1))
        topology = fine_topology(values[2].topology, values[0].grid.fine_span)
        surface.surface_z[(0, 0)] = -1
        with self.assertRaisesRegex(ValueError, "missing rim"):
            level_fill(surface.surface_z, ((0, 0),), 0, topology)

    def test_shared_refiner_preserves_known_interpolation(self):
        rows = ((0, 10), (20, 30))
        surface = refine_light_surface(0, 0, SurfaceGridSettings(fine_span=4, light_side=2),
            lambda x, y: rows[y][x], seed=1, z_min=-10, z_max=40,
            policy=ParentLightRefinePolicy(detail_noise_amplitude=0, z_band=0))
        self.assertEqual(tuple(surface.values()), (8, 12, 15, 15, 18, 22, 25, 25, 22, 28, 30, 30, 22, 28, 30, 30))
