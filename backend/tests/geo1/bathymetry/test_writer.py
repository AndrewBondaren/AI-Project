"""One atomic absolute writer, reservations and accepted overlap semantics."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.floorProfile import BasinFloorEvaluator
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace as Space
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.spatial.grid.gridBBox import GridBBox
from tests.geo1.bathymetry.fixtures import designed,surface


class FloorWriterTests(TestCase):
    def test_fine_writer_consumes_the_same_fixed_profile_without_coarse_scale(self):
        input,_,spec=designed(strategy=Strategy.PLATE_NOISE,span=3)
        coarse=surface(input)
        apply_basin_z(coarse,(spec,),input.topology,reserved=frozenset(),grid=input.grid)
        topology=spec.floor_profile.recipe.topology;b=topology.bounds
        fine=SurfaceHeightmap(world_uid=coarse.world_uid,bbox=GridBBox(b.x_min,b.x_max,b.y_min,b.y_max),
            surface_z={(x,y):99 for y in range(b.y_min,b.y_max+1) for x in range(b.x_min,b.x_max+1)})
        footprint=frozenset((3*x+1,3*y+1) for x,y in spec.footprint)
        apply_basin_z(fine,(replace(spec,footprint=footprint),),topology,reserved=frozenset(),
            coordinate_space=Space.WORLD_FINE_GRID)
        self.assertEqual({(3*x+1,3*y+1):coarse.surface_z[(x,y)] for x,y in spec.footprint},
            {c:fine.surface_z[c] for c in footprint})

    def test_field_write_is_absolute_reserved_and_idempotent_without_reselection(self):
        for strategy in (Strategy.CONTINENTAL_NOISE,Strategy.PLATE,Strategy.PLATE_NOISE):
            input,_,spec=designed(strategy=strategy);hm=surface(input);reserved=frozenset({min(spec.footprint)})
            evaluator=BasinFloorEvaluator(spec.floor_profile,topology=input.topology,
                coordinate_space=Space.WORLD_SURFACE_GRID,grid=input.grid)
            with patch.object(DesignedWaterPlacementPreparer,"prepare",side_effect=AssertionError("reselection")):
                count=apply_basin_z(hm,(spec,),input.topology,reserved=reserved,grid=input.grid)
                self.assertEqual(count,len(spec.footprint-reserved));first=dict(hm.surface_z)
                apply_basin_z(hm,(spec,),input.topology,reserved=reserved,grid=input.grid)
            self.assertEqual(hm.surface_z,first)
            for cell,z in hm.surface_z.items():
                self.assertEqual(z,evaluator.sample(cell) if cell in spec.footprint-reserved else 99)

    def test_sampled_floor_is_written_exactly_and_overlap_uses_minimum_absolute_z(self):
        input,_,spec=designed();cells=sorted(spec.footprint,key=lambda c:(c[1],c[0]))
        samples=tuple((c,-1-i) for i,c in enumerate(cells))
        sampled=replace(spec,source_uid="sampled",floor_z=-len(cells),
            floor_profile=SampledFloorProfile(space=Space.WORLD_SURFACE_GRID,samples=samples))
        expected=surface(input);apply_basin_z(expected,(spec,),input.topology,reserved=frozenset(),grid=input.grid)
        for order in ((spec,sampled),(sampled,spec)):
            hm=surface(input);apply_basin_z(hm,order,input.topology,reserved=frozenset(),grid=input.grid)
            self.assertEqual({c:hm.surface_z[c] for c in cells},{c:min(expected.surface_z[c],z) for c,z in samples})

    def test_bands_do_not_reinterpret_an_accepted_field(self):
        input,_,spec=designed();a=surface(input);b=surface(input)
        apply_basin_z(a,(spec,),input.topology,reserved=frozenset(),grid=input.grid)
        apply_basin_z(b,(replace(spec,bands=HydrologyBands(min=20,max=99)),),input.topology,reserved=frozenset(),grid=input.grid)
        self.assertEqual(a.surface_z,b.surface_z)

    def test_invalid_later_spec_cannot_leave_partial_writes(self):
        input,_,spec=designed();hm=surface(input);before=dict(hm.surface_z)
        scalar=replace(spec,source_uid="a",floor_profile=None)
        bad=replace(spec,source_uid="b",floor_profile=spec.floor_profile.model_copy(update={
            "recipe":spec.floor_profile.recipe.model_copy(update={"topology":input.topology})}))
        with self.assertRaises(ValueError):apply_basin_z(hm,(scalar,bad),input.topology,reserved=frozenset(),grid=input.grid)
        self.assertEqual(hm.surface_z,before)

    def test_sampled_space_mismatch_fails_without_writes(self):
        input,_,spec=designed();hm=surface(input);before=dict(hm.surface_z)
        sampled=replace(spec,floor_profile=SampledFloorProfile(space=Space.WORLD_FINE_GRID,
            samples=tuple((c,spec.floor_z) for c in sorted(spec.footprint,key=lambda c:(c[1],c[0])))))
        with self.assertRaises(ValueError):apply_basin_z(hm,(sampled,),input.topology,reserved=frozenset(),grid=input.grid)
        self.assertEqual(hm.surface_z,before)
