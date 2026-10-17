"""Coverage registry fields remain world data; no merge consumers cut over here."""

import copy
import unittest

from pydantic import ValidationError

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.hillShape import HillShape
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.terrainMasks.hillPolicy import HillPolicy as LegacyHillPolicy
from app.dataModel.terrainMasks.hillShape import HillShape as LegacyHillShape


class TerrainRegionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = WorldTerrainRegistry.canonical_defaults()
        self.masks = WorldTerrainMasks.canonical_defaults()
        self.custom_key = "steppe"
        self.custom_rank = 17
        self.custom_inertia = 2.5
        self.wire = {
            "system_terrain": self.custom_key, "terrain_category": "solid",
            "merge_rank": self.custom_rank, "inertia": self.custom_inertia,
            "eligibility": [
                {"fact": "climate.rainfall", "op": "gte", "lo": 20, "required": True},
                {"fact": "climate.rainfall", "op": "lte", "hi": 80},
                {"fact": "climate.temperature", "op": "in_range", "lo": 5, "hi": 30, "weight": 2},
                {"fact": "relief.elevation_plain", "op": "flag"},
            ],
            "hills": HillPolicy.canonical_plains().model_dump(mode="json"),
        }

    def test_new_fields_round_trip_through_world_column_validation(self):
        result = resolve_world_column("terrain_registry", [self.wire],
                                      ResolveContext.for_import(validate_only=True))
        entry = WorldTerrainRegistry.model_validate(result["terrain_registry"]).entry_for(self.custom_key)
        self.assertEqual(entry.merge_rank, self.custom_rank)
        self.assertEqual(entry.inertia, self.custom_inertia)
        self.assertTrue(all(isinstance(rule, EligibilityRule) for rule in entry.eligibility))
        self.assertTrue(entry.eligibility[0].required)
        self.assertIsInstance(entry.hills, HillPolicy)
        self.assertEqual(TerrainRegistryEntry.model_validate_json(entry.model_dump_json()), entry)

    def test_canonical_ranks_preserve_builtin_paint_order(self):
        order = tuple(policy.system_terrain for policy in (
            self.masks.default_roads, self.masks.default_ravines, self.masks.default_mountains,
            self.masks.default_forests, self.masks.default_plains,
        ))
        ranks = [self.registry.entry_for(key).merge_rank for key in order]
        self.assertEqual(ranks, sorted(set(ranks), reverse=True))
        for key, rank in zip(order, ranks):
            self.assertEqual(rank, len(order) - order.index(key))

    def test_canonical_hills_reuse_existing_policy_and_preserve_import_identity(self):
        self.assertIs(LegacyHillPolicy, HillPolicy)
        self.assertIs(LegacyHillShape, HillShape)
        for policy in (self.masks.default_forests, self.masks.default_plains):
            self.assertEqual(self.registry.entry_for(policy.system_terrain).hills, policy.hills)
        self.assertTrue(all(entry.inertia > 0 for entry in self.registry.root))

    def test_missing_fields_have_model_defaults_and_collections_are_independent(self):
        wire = {"system_terrain": self.custom_key, "terrain_category": "solid"}
        first = TerrainRegistryEntry.model_validate(wire)
        second = TerrainRegistryEntry.model_validate(wire)
        self.assertEqual(first.merge_rank, 0)
        self.assertEqual(first.inertia, 1.0)
        self.assertEqual(first.eligibility, [])
        self.assertIsNone(first.hills)
        self.assertIsNot(first.eligibility, second.eligibility)

    def test_malformed_rule_and_registry_fields_fail_without_repair(self):
        fact = self.wire["eligibility"][0]["fact"]
        flag_rule = {"fact": fact, "op": "flag"}
        bad_rules = (
            {**flag_rule, "op": "unknown"}, {"fact": fact, "op": "gte"},
            {"fact": fact, "op": "lte"}, {"fact": fact, "op": "in_range", "lo": 10, "hi": 1},
            {**flag_rule, "weight": -1}, {**flag_rule, "weight": float("inf")},
            {**flag_rule, "fact": ""}, {**flag_rule, "extra": True},
        )
        for rule in bad_rules:
            with self.subTest(rule=rule), self.assertRaises(ValidationError):
                EligibilityRule.model_validate(rule)
        for key, value in (("inertia", 0), ("inertia", -1), ("inertia", float("inf")),
                           ("merge_rank", None), ("eligibility", None), ("hills", {"radius": 0})):
            wire = copy.deepcopy(self.wire)
            wire[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                TerrainRegistryEntry.model_validate(wire)


if __name__ == "__main__":
    unittest.main()
