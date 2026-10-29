"""One caller view, full member content and authored-presence fingerprints."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.templateLibrary.templateContracts import ReliefTemplateSnapshot
from app.application.templateLibrary.templateSnapshotLoader import TemplateSnapshotLoader
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverTerrainPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.regions.regionState import RegionState
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from tests.geo1.support_sources.fixtures import UID,captured,fingerprint,members,sources,template


class SupportCaptureTests(TestCase):
    def test_parent_mask_gate_is_captured_separately_from_landcover_gate(self):
        a=captured(masks=WorldTerrainMasks(enabled=True))
        b=captured(masks=WorldTerrainMasks(enabled=False))
        self.assertEqual(a.landcover,b.landcover)
        self.assertTrue(a.masks_enabled);self.assertFalse(b.masks_enabled)
        self.assertNotEqual(fingerprint(a),fingerprint(b))

    def test_registry_omitted_and_explicit_null_hills_are_distinct_sources(self):
        a=TerrainRegistryEntry(system_terrain="plains",terrain_category="plains")
        b=TerrainRegistryEntry(system_terrain="plains",terrain_category="plains",hills=None)
        first=captured(terrain=WorldTerrainRegistry([a]));second=captured(terrain=WorldTerrainRegistry([b]))
        self.assertIsNone(first.terrain_entries[0].hills);self.assertIsNone(second.terrain_entries[0].hills)
        self.assertFalse(first.terrain_entries[0].hills_authored)
        self.assertTrue(second.terrain_entries[0].hills_authored)
        self.assertNotEqual(fingerprint(first),fingerprint(second))

    def test_template_body_and_membership_edits_change_the_fingerprint(self):
        first=captured();body=template().model_copy(update={"side_recipe":MountainSideRecipe(default_side_kind=ReliefSideKind.SLOPE)})
        second=captured(templates=members(body));removed=captured(templates=ReliefTemplateSnapshot("world"))
        self.assertEqual(first.templates[0][0],UID)
        self.assertNotEqual(fingerprint(first),fingerprint(second))
        self.assertNotEqual(fingerprint(first),fingerprint(removed))
        full_body=template().model_copy(update={"structure_refs":("some-member",)})
        self.assertNotEqual(fingerprint(first),fingerprint(captured(templates=members(full_body))))

    def test_region_state_and_shape_edits_are_part_of_the_source_fingerprint(self):
        masks=WorldTerrainMasks(declared_regions=[ForestSpec(name="forest",shape=BboxShape(x_min=0,x_max=1,y_min=0,y_max=1))])
        state=RegionState(region_uid="region",current_type="forest")
        value=captured(masks=masks,region_states=(state,))
        self.assertNotEqual(fingerprint(value),fingerprint(captured(masks=masks,region_states=(state.model_copy(update={"current_type":"plains"}),))))
        changed=WorldTerrainMasks(declared_regions=[ForestSpec(name="forest",shape=BboxShape(x_min=0,x_max=2,y_min=0,y_max=1))])
        self.assertNotEqual(fingerprint(value),fingerprint(captured(masks=changed,region_states=(state,))))

    def test_foreign_world_membership_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"same captured world"):
            captured(templates=replace(members(),world_uid="other"))

    def test_capture_never_loads_members_or_applies_domain_policy(self):
        with patch.object(TemplateSnapshotLoader,"load_relief",side_effect=AssertionError("IO")),patch.object(LandcoverTerrainPolicy,"apply_to",side_effect=AssertionError("domain policy")):
            self.assertEqual(captured(),captured())

    def test_omitted_and_explicit_null_hills_have_distinct_fingerprints(self):
        a=WorldTerrainMasks(default_landcover={"seed_spacing":1000,"terrain_policies":{"plains":{"system_terrain":"plains"}}})
        b=WorldTerrainMasks(default_landcover={"seed_spacing":1000,"terrain_policies":{"plains":{"system_terrain":"plains","hills":None}}})
        first=captured(masks=a);second=captured(masks=b)
        self.assertEqual(first.landcover.terrain_policies,second.landcover.terrain_policies)
        self.assertEqual(first.landcover.terrain_policy_hills_authored,())
        self.assertEqual(second.landcover.terrain_policy_hills_authored,("plains",))
        self.assertNotEqual(fingerprint(first),fingerprint(second))

    def test_mismatched_policy_dictionary_key_is_rejected(self):
        masks=WorldTerrainMasks(default_landcover={"seed_spacing":1000,"terrain_policies":{"wrong":{"system_terrain":"plains"}}})
        with self.assertRaisesRegex(ValueError,"key must equal"):captured(masks=masks)

    def test_mutating_source_collections_after_capture_cannot_change_the_input(self):
        data=sources();value=captured(**data);before=fingerprint(value)
        data["terrain"].root.clear();data["materials"].root.clear()
        data["masks"].declared_regions.clear()
        self.assertTrue(value.terrain_entries);self.assertTrue(value.materials)
        self.assertEqual(fingerprint(value),before)
