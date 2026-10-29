"""Full floor recipes survive production codec; changed schema invalidates refs."""
from dataclasses import replace
from unittest import TestCase
import os
from pathlib import Path
import subprocess
import sys

from app.application.encoding.canonicalCodec import encode,decode
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.surfacePlanning.surfacePlanBindings import surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as Slot
from tests.geo1.bathymetry.fixtures import designed


class FloorTransportTests(TestCase):
    def test_absolute_field_writes_replay_across_process_hash_seeds(self):
        script="from tests.geo1.bathymetry.fixtures import designed,surface; from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinZ import apply_basin_z; from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as S; i,d,s=designed(strategy=S.PLATE_NOISE); h=surface(i); apply_basin_z(h,(s,),i.topology,reserved=frozenset({min(s.footprint)}),grid=i.grid); print(sorted(h.surface_z.items()))"
        outputs=[]
        for seed in ("0","42"):
            outputs.append(subprocess.run([sys.executable,"-c",script],cwd=Path(__file__).resolve().parents[3],
                env={**os.environ,"PYTHONHASHSEED":seed},capture_output=True,text=True,check=True).stdout)
        self.assertEqual(outputs[0],outputs[1])

    def test_full_recipes_scalar_and_sampled_profiles_round_trip_in_production_manifest(self):
        for strategy in (Strategy.CONTINENTAL_NOISE,Strategy.PLATE,Strategy.PLATE_NOISE):
            _,_,spec=designed(strategy=strategy)
            sampled=replace(spec,floor_profile=SampledFloorProfile(space=CoordinateSpace.WORLD_SURFACE_GRID,
                samples=tuple((c,spec.floor_z) for c in sorted(spec.footprint,key=lambda c:(c[1],c[0])))))
            for value in (spec,replace(spec,floor_profile=None),sampled):
                encoded=encode(value,SURFACE_MANIFEST)
                self.assertEqual(decode(encoded,BasinSpec,SURFACE_MANIFEST),value)
                self.assertEqual(encode(value,SURFACE_MANIFEST),encoded)

    def test_water_schema_cache_and_dependency_contracts_move_together(self):
        binding=surface_plan_binding(Slot.WATER_PLACEMENT)
        self.assertEqual(binding.metadata.schema_version,2)
        self.assertEqual(binding.cache_schema_version,2)
        for slot in (Slot.RELIEF,Slot.HYDROLOGY_ROUTES):
            upstream=next(d for d in surface_plan_binding(slot).dependency_contracts() if d.slot==Slot.WATER_PLACEMENT.value)
            self.assertEqual(upstream.schema_version,2)
