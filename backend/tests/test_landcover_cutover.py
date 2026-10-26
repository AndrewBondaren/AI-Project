"""10b: one policy, read aliases and independent default/custom/mixed fixtures."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from pydantic import ValidationError, create_model

from app.application.jsonValidation.facade import normalize_world, merge_world_patch
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import terrain, terrain_masks
from app.application.worldData.generators.terrain.terrainZ import surface_biome_terrain
from app.application.worldData.regions.coverageBackground import surface_coverage
from app.application.worldData.pack.bake.lightGrid.contributors.landcoverBackground import background_key_for_zone
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.masks.enums.maskDomainId import MaskDomainId, MASK_DOMAIN_CONTRIBUTOR
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import (
    LandcoverClaimNoise, LandcoverRegionsCategoryPolicy, LandcoverTerrainPolicy,
)
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.meta.worldGridSettings import WorldGridSettings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"world_landcover_{name}.json").read_text(encoding="utf-8"))


class LandcoverCutoverTests(unittest.TestCase):
    def test_only_one_landcover_domain(self):
        self.assertEqual({domain.value for domain in MASK_DOMAIN_CONTRIBUTOR
                          if MASK_DOMAIN_CONTRIBUTOR[domain].value == "landcover"}, {"landcover"})
        self.assertEqual(MaskDomainId("landcover"), MaskDomainId.LANDCOVER)
        self.assertNotIn("default_forests", WorldTerrainMasks.model_fields)
        self.assertNotIn("default_plains", WorldTerrainMasks.model_fields)

    def test_default_fixture_is_minimal_and_uses_canonical_root(self):
        world = fixture("default")["world"]
        self.assertNotIn("terrain_masks", world)
        policy = terrain_masks(SimpleNamespace(**world)).default_landcover
        self.assertEqual(policy, LandcoverRegionsCategoryPolicy.canonical_defaults())
        self.assertEqual(policy.seed_spacing, 1000)
        self.assertEqual((policy.max_radius, policy.claim_noise.amplitude,
                          policy.claim_noise.scale, policy.transition_threshold), (2250, 125, 250, 1))

    def test_custom_fixture_explicit_at_every_policy_level_and_stable(self):
        world = fixture("custom")["world"]
        raw = world["terrain_masks"]["default_landcover"]
        self.assertEqual(set(world["terrain_masks"]), set(WorldTerrainMasks.model_fields))
        for row in world["terrain_registry"]:
            self.assertEqual(set(row), set(TerrainRegistryEntry.model_fields))
        self.assertEqual(set(raw), set(LandcoverRegionsCategoryPolicy.model_fields))
        self.assertEqual(set(raw["claim_noise"]), set(LandcoverClaimNoise.model_fields))
        for override in raw["terrain_policies"].values():
            self.assertEqual(set(override), set(LandcoverTerrainPolicy.model_fields))
            self.assertEqual(set(override["hills"]), set(HillPolicy.model_fields))
        result = LandcoverRegionsCategoryPolicy.model_validate(raw)
        self.assertEqual(result.model_dump(mode="json"), raw)
        # Deliberately different defaults: explicit fixture values must still win.
        ChangedDefaults = create_model("ChangedLandcoverDefaults", __base__=LandcoverRegionsCategoryPolicy,
            max_radius=(int, 99), transition_threshold=(float, .2),
            claim_noise=(LandcoverClaimNoise, LandcoverClaimNoise(amplitude=1, scale=2)),
            fallback_terrain=(str, "other"))
        self.assertEqual(ChangedDefaults.model_validate(raw).model_dump(mode="json"), raw)
        self.assertEqual(WorldGridSettings.model_validate(world).fine_cells_per_map_cell, 2000)

    def test_mixed_fixture_fills_only_omitted_fields_and_round_trips(self):
        raw = fixture("mixed")["world"]["terrain_masks"]
        policy = WorldTerrainMasks.model_validate(raw).default_landcover
        self.assertEqual(policy.seed_spacing, 1000)
        self.assertEqual(policy.transition_threshold, .6)
        self.assertEqual(policy.claim_noise.amplitude, 60)
        canonical = LandcoverRegionsCategoryPolicy.canonical_defaults()
        self.assertEqual(policy.claim_noise.scale, canonical.claim_noise.scale)
        self.assertEqual(policy.max_radius, canonical.max_radius)
        self.assertEqual(policy.fallback_terrain, canonical.fallback_terrain)
        self.assertEqual(LandcoverRegionsCategoryPolicy.model_validate(policy.model_dump()), policy)

    def test_seed_contract_unchanged_and_invalid_supplied_knobs_do_not_default(self):
        self.assertTrue(LandcoverRegionsCategoryPolicy.model_fields["seed_spacing"].is_required())
        with self.assertRaises(ValidationError):
            LandcoverRegionsCategoryPolicy()
        self.assertEqual(LandcoverRegionsCategoryPolicy(seed_spacing=600).seed_spacing, 600)
        for raw in ({"seed_spacing": 0}, {"seed_spacing": 1000, "max_radius": 0},
                    {"seed_spacing": 1000, "claim_noise": {"scale": 0}},
                    {"seed_spacing": 1000, "claim_noise": {"amplitude": -1}}):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                LandcoverRegionsCategoryPolicy.model_validate(raw)
        for overrides in (None, {"forest": "invalid"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                WorldTerrainMasks.model_validate({"default_forests": {},
                    "default_landcover": {"seed_spacing": 1000, "terrain_policies": overrides}})

    def test_legacy_aliases_read_once_and_emit_only_new_wire(self):
        raw = {"default_forests": {"forest_min_rainfall": 60, "hills": {"radius": 17}},
               "default_plains": {"system_terrain": "steppe"}}
        original = copy.deepcopy(raw)
        masks = WorldTerrainMasks.model_validate(raw)
        dumped = masks.model_dump(mode="json")
        self.assertEqual(raw, original)
        self.assertNotIn("default_forests", dumped)
        self.assertNotIn("default_plains", dumped)
        self.assertEqual(masks.default_landcover.fallback_terrain, "steppe")
        self.assertEqual(masks.default_landcover.terrain_policies["forest"].min_rainfall, 60)
        self.assertEqual(WorldTerrainMasks.model_validate(dumped), masks)
        canonical_explicit = LandcoverRegionsCategoryPolicy(seed_spacing=1000,
            fallback_terrain="plains").model_dump(mode="json")
        both = WorldTerrainMasks.model_validate({**raw, "default_landcover": canonical_explicit})
        self.assertEqual(both.default_landcover.fallback_terrain, "plains")

    def test_alias_patch_preserves_other_fields_and_hills_presence(self):
        base = normalize_world({"terrain_masks": {"default_forests": {
            "forest_min_rainfall": 60, "hills": {"radius": 17}}}})
        patch_wire = normalize_world({"terrain_masks": {"default_forests": {"enabled": False}}}, partial=True)
        merged = normalize_world(merge_world_patch(base, patch_wire))
        override = merged["terrain_masks"]["default_landcover"]["terrain_policies"]["forest"]
        self.assertEqual(override["min_rainfall"], 60)
        self.assertEqual(override["hills"]["radius"], 17)
        self.assertFalse(override["enabled"])
        for value in ({"system_terrain": "forest"}, {"system_terrain": "forest", "hills": None}):
            state = LandcoverTerrainPolicy.model_validate(value)
            restored = LandcoverTerrainPolicy.model_validate(state.model_dump(mode="json"))
            self.assertEqual("hills" in restored.model_fields_set, "hills" in value)

    def test_custom_n_plus_one_background_uses_world_registry(self):
        world = SimpleNamespace(**normalize_world(fixture("custom")["world"]))
        registry = terrain(world)
        policy = terrain_masks(world).default_landcover
        self.assertEqual(surface_coverage(registry=registry, policy=policy,
            system_climate_zone=ClimateZone.ARID.system_climate), "steppe")
        self.assertEqual(surface_biome_terrain(set(e.system_terrain for e in registry.root),
            terrain_registry=registry, masks=terrain_masks(world),
            system_climate_zone=ClimateZone.ARID.system_climate), "steppe")
        self.assertEqual(registry.entry_for("forest").hills.radius, 35)

    def test_legacy_fixture_files_normalize_without_editing(self):
        for name in ("world_test_002", "world_template", "world_terrain_test"):
            world = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["world"]
            before = copy.deepcopy(world)
            normalized = normalize_world(world)
            self.assertEqual(world, before)
            WorldTerrainMasks.model_validate(normalized.get("terrain_masks", {}))

    def test_missing_policy_terrain_references_reject_before_write(self):
        for policy in ({"seed_spacing": 1000, "fallback_terrain": "missing"},
                       {"seed_spacing": 1000, "terrain_policies": {
                           "forest": {"system_terrain": "missing"}}}):
            with self.subTest(policy=policy), self.assertRaises(ImportValidationError) as error:
                normalize_world({"terrain_masks": {"default_landcover": policy}})
            self.assertTrue(any(issue.code == "REF_W_UNKNOWN" for issue in error.exception.errors))
        for partial in (False, True):
            with self.subTest(partial=partial), self.assertRaises(ImportValidationError):
                normalize_world({"terrain_masks": {"default_forests": {
                    "forest_min_rainfall": None}}}, partial=partial)

    def test_background_observes_world_climate_profile_override(self):
        zone = ClimateZone.ARID
        world = SimpleNamespace(world_uid="climate-override", terrain_registry=None, terrain_masks=None,
            climate_zone_registry=[{**zone.to_entry().model_dump(mode="json"), "base_rainfall": 80}])
        registry = terrain(world)
        result = background_key_for_zone(zone.world_map_wire_id(), terrain_masks(world),
            {e.system_terrain for e in registry.root}, registry, world=world)
        self.assertEqual(result, WorldTerrainRegistry.forest_terrain_key())


if __name__ == "__main__":
    unittest.main()
