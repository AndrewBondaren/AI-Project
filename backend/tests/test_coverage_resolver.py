"""Scoring, missing channels, deterministic choices and interim climate rules."""

from itertools import permutations
import unittest

from app.application.worldData.regions.coverageResolver import resolve
from app.application.worldData.regions.regionFacts import ClimateFacts, RegionFacts, ReliefFacts
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.enums.eligibilityOp import EligibilityOp
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry



def candidate(key, *rules):
    return TerrainRegistryEntry(system_terrain=key, terrain_category="solid", eligibility=list(rules))


def rainfall(op=EligibilityOp.GTE, **kwargs):
    return EligibilityRule(fact="climate.rainfall", op=op, **kwargs)


class CoverageResolverTests(unittest.TestCase):
    def setUp(self):
        self.facts = RegionFacts(climate=ClimateFacts(rainfall_mean=60))

    def test_required_failure_removes_otherwise_high_scoring_candidate(self):
        blocked = candidate("blocked", rainfall(lo=70, required=True, weight=0),
                            rainfall(lo=10, weight=100))
        winner = candidate("winner", rainfall(lo=40))
        self.assertEqual(resolve(self.facts, WorldTerrainRegistry([blocked, winner])).target_key, "winner")

    def test_argmax_uses_weighted_sum_not_normalized_strength(self):
        weak = candidate("weak", rainfall(lo=60, weight=10))  # score 5, strength .5
        strong = candidate("strong", rainfall(lo=20, weight=1))  # score 1, strength 1
        result = resolve(self.facts, WorldTerrainRegistry([strong, weak]))
        self.assertEqual(result.target_key, "weak")
        self.assertAlmostEqual(result.strength, 0.5)

    def test_equal_weights_choose_greater_satisfaction(self):
        entries = [candidate("dry", rainfall(EligibilityOp.LTE, hi=40)),
                   candidate("wet", rainfall(lo=40))]
        result = resolve(self.facts, WorldTerrainRegistry(entries))
        self.assertEqual(result.target_key, "wet")
        self.assertAlmostEqual(result.strength, 0.75)

    def test_permutations_and_score_ties_have_identical_result(self):
        entries = [candidate(key, rainfall(lo=40)) for key in ("zeta", "alpha", "beta")]
        results = [resolve(self.facts, WorldTerrainRegistry(list(order))) for order in permutations(entries)]
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(results[0].target_key, "alpha")

    def test_unresolved_has_warning_no_fallback_and_does_not_mutate_inputs(self):
        registry = WorldTerrainRegistry([candidate("wet", rainfall(lo=80, required=True))])
        before = registry.model_dump()
        current_type = "steppe"
        with self.assertLogs("app.application.worldData.regions.coverageResolver", level="WARNING") as logs:
            result = resolve(self.facts, registry)
        if result is not None:
            current_type = result.target_key
        self.assertIsNone(result)
        self.assertEqual(current_type, "steppe")
        self.assertEqual(registry.model_dump(), before)
        self.assertEqual(self.facts.climate.rainfall_mean, 60)
        self.assertIn("landcover | resolve_unresolved | WarningError", logs.output[0])
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(resolve(self.facts, WorldTerrainRegistry([])))

    def test_flora_unknown_fact_and_absent_domain_score_zero(self):
        for fact in ("flora.eligible_trees", "missing.value", "climate.unknown", "hydrology.water_table"):
            for required in (False, True):
                rule = EligibilityRule(fact=fact, op=EligibilityOp.FLAG, required=required)
                registry = WorldTerrainRegistry([candidate("custom", rule)])
                if required:
                    with self.assertLogs(level="WARNING"):
                        self.assertIsNone(resolve(self.facts, registry))
                else:
                    self.assertEqual(resolve(self.facts, registry).strength, 0)

    def test_required_inclusive_bounds_and_range_falloff(self):
        for op, bounds, value in ((EligibilityOp.GTE, {"lo": 0}, 0), (EligibilityOp.LTE, {"hi": -10}, -10),
                                  (EligibilityOp.IN_RANGE, {"lo": 10, "hi": 20}, 10),
                                  (EligibilityOp.IN_RANGE, {"lo": 10, "hi": 20}, 20)):
            registry = WorldTerrainRegistry([candidate("custom", rainfall(op, required=True, **bounds))])
            self.assertIsNotNone(resolve(RegionFacts(climate=ClimateFacts(rainfall_mean=value)), registry))
        registry = WorldTerrainRegistry([candidate("custom", rainfall(EligibilityOp.IN_RANGE, lo=10, hi=20))])
        for value, expected in ((0, 0), (5, .5), (10, 1), (15, 1), (20, 1), (25, .5), (30, 0)):
            self.assertAlmostEqual(resolve(RegionFacts(climate=ClimateFacts(rainfall_mean=value)), registry).strength,
                                   expected)

    def test_flag_zero_weight_empty_rules_and_nonfinite_facts(self):
        rule = EligibilityRule(fact="relief.elevation_plain", op=EligibilityOp.FLAG, required=True, weight=0)
        registry = WorldTerrainRegistry([candidate("custom", rule)])
        self.assertEqual(resolve(RegionFacts(relief=ReliefFacts(elevation_plain=True)), registry).strength, 0)
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(resolve(RegionFacts(relief=ReliefFacts(elevation_plain=False)), registry))
        self.assertEqual(resolve(self.facts, WorldTerrainRegistry([candidate("custom")])).strength, 0)
        for value in (float("nan"), float("inf")):
            registry = WorldTerrainRegistry([candidate("custom", rainfall(lo=10, required=True))])
            with self.assertLogs(level="WARNING"):
                self.assertIsNone(resolve(RegionFacts(climate=ClimateFacts(rainfall_mean=value)), registry))

    def test_canonical_climate_rules_match_legacy_threshold(self):
        registry = WorldTerrainRegistry.canonical_defaults()
        forest = registry.entry_for(registry.forest_terrain_key())
        threshold = WorldTerrainRegistry.forest_min_rainfall()
        self.assertEqual(forest.eligibility[0].lo, threshold)
        self.assertTrue(forest.eligibility[0].required)
        for rain in (0, threshold - 1, threshold, threshold + 1, 100):
            facts = RegionFacts(climate=ClimateFacts(rainfall_mean=rain))
            result = resolve(facts, registry)
            expected = registry.forest_terrain_key() if rain >= threshold else registry.plains_terrain_key()
            self.assertEqual(result.target_key, expected)
        with self.assertLogs(level="WARNING"):
            self.assertIsNone(resolve(RegionFacts(climate=ClimateFacts(rainfall_mean=0)),
                                      WorldTerrainRegistry([forest])))


if __name__ == "__main__":
    unittest.main()
