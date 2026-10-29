"""Absolute field depth arithmetic and sample/field frame invariants."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.generators.terrain.reliefObjects.bathymetry.floorProfile import BasinFloorEvaluator
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace as Space
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile, SampledFloorProfile
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.geo1.bathymetry.fixtures import designed


class FloorProfileTests(TestCase):
    def test_signed_water_depth_half_up_and_minimum_one(self):
        input,_,spec=designed()
        profile=FieldFloorProfile(recipe=spec.floor_profile.recipe,level=10,depth=5,z_min=0)
        evaluator=BasinFloorEvaluator(profile,topology=input.topology,coordinate_space=Space.WORLD_SURFACE_GRID,grid=input.grid)
        for value,z in ((-1.,5),(-.8,5),(-.4,6),(0.,7),(.4,8),(.8,9),(1.,9)):
            with self.subTest(value=value),patch.object(NoiseFieldGenerator,"sample",return_value=value):
                self.assertEqual(evaluator.sample((-1,0)),z)
        profile=profile.model_copy(update={"z_min":8})
        with patch.object(NoiseFieldGenerator,"sample",return_value=-1.):
            self.assertEqual(BasinFloorEvaluator(profile,topology=input.topology,
                coordinate_space=Space.WORLD_SURFACE_GRID,grid=input.grid).sample((-1,0)),8)

    def test_coarse_and_fine_centers_match_for_all_recipes_and_topologies(self):
        for strategy in (Strategy.CONTINENTAL_NOISE,Strategy.PLATE,Strategy.PLATE_NOISE):
            for mode in Mode:
                input,_,spec=designed(strategy=strategy,mode=mode,span=3)
                profile=spec.floor_profile
                coarse=BasinFloorEvaluator(profile,topology=input.topology,coordinate_space=Space.WORLD_SURFACE_GRID,grid=input.grid)
                fine=BasinFloorEvaluator(profile,topology=profile.recipe.topology,coordinate_space=Space.WORLD_FINE_GRID,grid=None)
                for x,y in spec.footprint:
                    self.assertEqual(coarse.sample((x,y)),fine.sample((3*x+1,3*y+1)))

    def test_plate_layout_is_built_once_for_the_evaluator(self):
        input,_,spec=designed(strategy=Strategy.PLATE_NOISE)
        with patch.object(PlateFieldGenerator,"layout",wraps=PlateFieldGenerator().layout) as layout:
            evaluator=BasinFloorEvaluator(spec.floor_profile,topology=input.topology,
                coordinate_space=Space.WORLD_SURFACE_GRID,grid=input.grid)
            for cell in spec.footprint:evaluator.sample(cell)
            self.assertEqual(layout.call_count,1)

    def test_profile_bounds_and_raw_payloads_are_rejected_at_spec_boundary(self):
        _,_,spec=designed()
        for update in ({"floor_z":spec.floor_z-1},{"z_water_level":spec.z_water_level+1},
                       {"floor_profile":spec.floor_profile.model_dump()},
                       {"floor_profile":spec.floor_profile.model_copy(update={"z_min":spec.z_water_level})}):
            with self.subTest(update=update),self.assertRaises((ValueError,TypeError)):replace(spec,**update)

    def test_sampled_profile_requires_exact_cells_minimum_and_below_level(self):
        _,_,spec=designed();cells=tuple(sorted(spec.footprint,key=lambda c:(c[1],c[0])))
        profile=SampledFloorProfile(space=Space.WORLD_SURFACE_GRID,samples=tuple((c,-5) for c in cells))
        valid=replace(spec,floor_profile=profile,floor_z=-5)
        self.assertEqual(valid.floor_profile,profile)
        for bad in (profile.model_copy(update={"samples":profile.samples[:-1]}),
                    profile.model_copy(update={"samples":tuple((c,0) for c in cells)}),
                    profile.model_copy(update={"space":Space.LOCATION_FINE_GRID})):
            with self.assertRaises(ValueError):replace(valid,floor_profile=bad)
        with self.assertRaises(ValueError):replace(valid,floor_z=-6)

    def test_frame_requires_captured_scale_and_canonical_cells(self):
        input,_,spec=designed()
        with self.assertRaises(TypeError):BasinFloorEvaluator(spec.floor_profile,topology=input.topology,
            coordinate_space=Space.WORLD_SURFACE_GRID,grid=None)
        with self.assertRaises(ValueError):BasinFloorEvaluator(spec.floor_profile,topology=input.topology,
            coordinate_space=Space.WORLD_FINE_GRID,grid=None)
        evaluator=BasinFloorEvaluator(spec.floor_profile,topology=input.topology,
            coordinate_space=Space.WORLD_SURFACE_GRID,grid=input.grid)
        for cell in ((999,0),(True,0)):
            with self.assertRaises(ValueError):evaluator.sample(cell)
