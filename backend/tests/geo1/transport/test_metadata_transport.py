"""Single source metadata transport across preparation, P2 and scalar specs."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.generators.hydrology.basinSpecFactory import basin_specs
from app.application.worldData.generators.hydrology.sources.waterSourceMetadataFactory import WaterSourceMetadataFactory
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateNoiseStrategy import PlateNoiseStrategy
from app.application.worldData.placement.adapters import water
from app.application.worldData.placement.adapters.waterTypes import PreparedWaterEntry
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredLakeSource, WaterDesignSourceKind
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.placement import PlacementIdentity, ResolvedPlacement
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from tests.geo1.composition.fixtures import case
from tests.test_water_placement_adapter import basin, coast, context, lake, prepare, resolve


class MetadataTransportTests(TestCase):
    def test_policy_values_are_captured_before_p2_and_factory_uses_only_metadata(self):
        snap=context(auto={"coast":1});prep=prepare(coasts=[coast()],snapshot=snap,
            default_water_level=7,default_seas={"basin_depth":13,"bands":{"min":3,"max":8}})
        entry=prep.entries[0]
        self.assertEqual((entry.source.level,entry.floor_z,entry.source.default_depth),(7,-6,13))
        self.assertEqual(entry.source.source_path,("water_sources","coast"))
        self.assertEqual(entry.source.source_kind,WaterDesignSourceKind.COASTLINE)
        _,records=resolve(prep,snap)
        with patch.object(WaterSourceMetadataFactory,"build",side_effect=AssertionError("metadata repeated")):
            spec=basin_specs(prep,records)[0]
        self.assertEqual((spec.bands.min,spec.bands.max),(3,8))
        self.assertEqual((spec.floor_z,spec.z_water_level),(-6,7))
        self.assertFalse(hasattr(entry.source,"location_uid"))
        self.assertFalse(hasattr(entry,"kind"))

    def test_lake_rim_is_calculated_once_and_preserved_through_mapper(self):
        snap=context(auto={"lake":1})
        with patch.object(water,"lake_level",wraps=water.lake_level) as rim:
            prep=prepare(lakes=[lake()],snapshot=snap,default_water_level=99,
                default_lakes={"basin_depth":6,"bands":{"min":2,"max":4}})
            _,records=resolve(prep,snap);spec=basin_specs(prep,records)[0]
        self.assertEqual(rim.call_count,1)
        self.assertEqual((spec.z_water_level,spec.floor_z),(3,-3))
        self.assertEqual(spec.bands,prep.entries[0].source.bands)

    def test_basin_explicit_level_and_rim_override_are_captured(self):
        snap=context();prep=prepare(basins=[basin(z_water_level=5,rim={"min":4,"max":9})],snapshot=snap)
        _,records=resolve(prep,snap);spec=basin_specs(prep,records)[0]
        self.assertEqual((spec.z_water_level,spec.floor_z,spec.bands.min,spec.bands.max),(5,-20,4,9))

    def test_procedural_source_without_location_uid_uses_the_same_entry_and_mapper(self):
        input=case();draft=PlateNoiseStrategy().design(input)
        metadata=WaterSourceMetadataFactory().build(input.source,default_water_level=FineZ(0),
            seas=HydrologySeasPolicy(basin_depth=input.metadata.default_depth),lakes=HydrologyLakesPolicy(),
            rim_level=None,source_path=("water_sources",input.metadata.source_uid))
        snap=context();prep=prepare(basins=[basin()],snapshot=snap)
        old=prep.entries[0].prepared
        identity=PlacementIdentity(world_uid=prep.world_uid,source_uid=metadata.source_uid,region_uid=metadata.source_uid)
        prepared=old.model_copy(update={"intent":old.intent.model_copy(update={"identity":identity})})
        entry=PreparedWaterEntry(source=metadata,prepared=prepared,floor_z=draft.floor_z,floor_profile=draft.floor_profile)
        prep=replace(prep,entries=(entry,))
        _,records=resolve(prep,snap)
        self.assertEqual(records[0].source_uid,input.metadata.source_uid)
        self.assertEqual(records[0].kind,metadata.body_kind)
        self.assertEqual(prep.entries[0].floor_profile,draft.floor_profile)
        # G9 consumes this retained profile; G8-A only migrates scalar specs.
        self.assertIsNotNone(prep.entries[0].floor_profile)
        with self.assertRaisesRegex(ValueError,"profiled water"):
            basin_specs(prep,records)

    def test_metadata_mismatch_cannot_be_reinterpreted_as_a_different_spec(self):
        snap=context();prep=prepare(basins=[basin()],snapshot=snap);_,records=resolve(prep,snap)
        for update in ({"z_water_level":7},{"kind":BasinKind.LAKE},{"liquid":"lava"}):
            with self.subTest(update=update),self.assertRaisesRegex(ValueError,"metadata"):
                basin_specs(prep,(records[0].model_copy(update=update),))

    def test_same_uid_with_different_preparation_is_rejected(self):
        snap=context();prep=prepare(basins=[basin()],snapshot=snap);_,records=resolve(prep,snap)
        original=records[0].placement.prepared
        changed=original.model_copy(update={"original_area":999.0})
        placement=ResolvedPlacement(prepared=changed,candidate_uid=records[0].placement.candidate_uid)
        with self.assertRaisesRegex(ValueError,"exact prepared"):
            basin_specs(prep,(records[0].model_copy(update={"placement":placement}),))

    def test_duplicate_sources_are_rejected_instead_of_dict_overwrite(self):
        snap=context();prep=prepare(basins=[basin()],snapshot=snap);_,records=resolve(prep,snap)
        with self.assertRaisesRegex(ValueError,"duplicate prepared"):
            basin_specs(replace(prep,entries=prep.entries*2),records)
        with self.assertRaisesRegex(ValueError,"duplicate resolved"):
            basin_specs(prep,records*2)

    def test_entry_rejects_raw_payload_wrong_identity_and_invalid_floor(self):
        entry=prepare(basins=[basin()]).entries[0]
        for update in ({"source":entry.source.model_dump()},{"floor_profile":{}},
                       {"source":entry.source.model_copy(update={"source_uid":"another"})},
                       {"floor_z":True},{"floor_z":entry.source.level}):
            with self.subTest(update=update),self.assertRaises((ValueError,TypeError)):
                replace(entry,**update)

    def test_lake_metadata_requires_ready_rim_and_non_lake_rejects_it(self):
        source=AuthoredLakeSource(value=DeclaredLake.model_validate(lake()))
        factory=WaterSourceMetadataFactory()
        with self.assertRaisesRegex(ValueError,"rim"):
            factory.build(source,default_water_level=FineZ(0),seas=HydrologySeasPolicy(),
                lakes=HydrologyLakesPolicy(),rim_level=None,source_path=("water_sources","lake"))
        with self.assertRaisesRegex(ValueError,"rim"):
            factory.build(case().source,default_water_level=FineZ(0),seas=HydrologySeasPolicy(),
                lakes=HydrologyLakesPolicy(),rim_level=FineZ(3),source_path=("water_sources","source"))

    def test_field_profile_cannot_disagree_with_captured_metadata(self):
        draft=PlateNoiseStrategy().design(case());entry=prepare(basins=[basin()]).entries[0]
        metadata=entry.source.model_copy(update={"level":draft.metadata.level,"default_depth":draft.metadata.default_depth})
        entry=replace(entry,source=metadata,floor_z=draft.floor_z,floor_profile=draft.floor_profile)
        for update in ({"floor_z":FineZ(-100)},
                       {"source":metadata.model_copy(update={"level":FineZ(1)})}):
            with self.subTest(update=update),self.assertRaisesRegex(ValueError,"field floor"):
                replace(entry,**update)
