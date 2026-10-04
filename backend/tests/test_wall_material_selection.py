"""S5: material policy consumers + wall material selector — §11/§8.7.1."""
import unittest

from app.application.economy.materialPolicies.defaultMaterialPolicyConsumer import (
    DefaultMaterialPolicyConsumer,
)
from app.application.economy.materialPolicies.materialPolicyConsumer import (
    MaterialPolicyConsumer,
)
from app.application.worldData.generators.structure.wallMaterials import (
    select_wall_materials,
)
from app.application.worldData.generators.structure.wallRegions import (
    classify_wall_regions,
)
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.economy.materialPolicies import (
    BuildingEconomicContext,
    MaterialCandidate,
    MaterialPolicy,
    MaterialPolicyFailure,
    MaterialPolicyRequest,
)
from app.dataModel.locations.structure.wallRegion import WallProvenance
from tests.test_u_shape_orientation_baseline import room

STRENGTHS = {"brick": 0.5, "wood": 0.3, "granite": 0.8, "marble": 0.8}


def context(band):
    return BuildingEconomicContext(economic_tier="basic", band=band)


def candidate(material, strength, key, area=10):
    return MaterialCandidate(system_material=material,
                             structural_strength=strength,
                             source_key=key, source_area=area)


def request(candidates, policy=None, band=EconomicTierBand.COMMON):
    return MaterialPolicyRequest(candidates=tuple(candidates), policy=policy,
                                 context=context(band))


def two_room_setup():
    """Adjacent rooms sharing partition column x=6, interior cells y=1..3."""
    a = room("a", x=0, y=0, width=7, depth=5)
    a.wall_material = "wood"
    b = room("b", x=6, y=0, width=7, depth=5)
    b.wall_material = "granite"
    return classify_wall_regions([a, b], 0, 3), {a.uid_key: a, b.uid_key: b}


class MaterialPolicyConsumerTests(unittest.TestCase):
    def test_explicit_max_and_min_pick_by_strength(self):
        candidates = [candidate("wood", 0.3, "a"), candidate("granite", 0.8, "b")]
        consumer = MaterialPolicyConsumer()
        decision = consumer.decide(
            request(candidates, policy=MaterialPolicy.MAX_STRENGTH))
        self.assertEqual(decision.candidate.system_material, "granite")
        decision = consumer.decide(
            request(candidates, policy=MaterialPolicy.MIN_STRENGTH))
        self.assertEqual(decision.candidate.system_material, "wood")

    def test_explicit_policy_ignores_economic_context(self):
        decision = MaterialPolicyConsumer().decide(request(
            [candidate("wood", 0.3, "a"), candidate("granite", 0.8, "b")],
            policy=MaterialPolicy.MIN_STRENGTH, band=EconomicTierBand.RICH))
        self.assertEqual(decision.candidate.system_material, "wood")

    def test_missing_policy_is_a_routing_contract_violation(self):
        with self.assertRaises(ValueError):
            MaterialPolicyConsumer().decide(
                request([candidate("wood", 0.3, "a")]))

    def test_tie_break_larger_area_then_first_candidate(self):
        decision = MaterialPolicyConsumer().decide(request(
            [candidate("wood", 0.5, "small", area=9),
             candidate("oak", 0.5, "big", area=25)],
            policy=MaterialPolicy.MAX_STRENGTH))
        self.assertEqual(decision.candidate.system_material, "oak")
        decision = MaterialPolicyConsumer().decide(request(
            [candidate("wood", 0.5, "a", area=9),
             candidate("oak", 0.5, "b", area=9)],
            policy=MaterialPolicy.MIN_STRENGTH))
        self.assertEqual(decision.candidate.system_material, "wood")

    def test_missing_strength_is_structured_failure_not_zero(self):
        candidates = [candidate("wood", 0.3, "a"), candidate("mystery", None, "b")]
        for policy in (MaterialPolicy.MAX_STRENGTH, MaterialPolicy.MIN_STRENGTH):
            with self.subTest(policy=policy):
                decision = MaterialPolicyConsumer().decide(
                    request(candidates, policy=policy))
                self.assertIsNone(decision.candidate)
                self.assertEqual(decision.failure,
                                 MaterialPolicyFailure.MISSING_STRENGTH)

    def test_no_candidates_is_structured_failure(self):
        decision = MaterialPolicyConsumer().decide(
            request([], policy=MaterialPolicy.MAX_STRENGTH))
        self.assertIsNone(decision.candidate)
        self.assertEqual(decision.failure, MaterialPolicyFailure.NO_CANDIDATES)


class DefaultMaterialPolicyConsumerTests(unittest.TestCase):
    def test_rich_context_picks_strongest(self):
        decision = DefaultMaterialPolicyConsumer().decide(request(
            [candidate("wood", 0.3, "a"), candidate("granite", 0.8, "b")],
            band=EconomicTierBand.RICH))
        self.assertEqual(decision.candidate.system_material, "granite")
        self.assertEqual(decision.policy, MaterialPolicy.MAX_STRENGTH)

    def test_non_rich_contexts_pick_weakest(self):
        candidates = [candidate("wood", 0.3, "a"), candidate("granite", 0.8, "b")]
        for band in (EconomicTierBand.POOR, EconomicTierBand.COMMON,
                     EconomicTierBand.MIDDLE, EconomicTierBand.WEALTHY):
            with self.subTest(band=band):
                decision = DefaultMaterialPolicyConsumer().decide(
                    request(candidates, band=band))
                self.assertEqual(decision.candidate.system_material, "wood")
                self.assertEqual(decision.policy, MaterialPolicy.MIN_STRENGTH)


class WallMaterialSelectorTests(unittest.TestCase):
    def plan(self, regions, rooms, band=EconomicTierBand.COMMON, policy=None,
             strengths=STRENGTHS, building="brick"):
        return select_wall_materials(regions, rooms, building, strengths,
                                     context(band), policy)

    def material_at(self, choices, cell):
        hits = [c.system_material for c in choices if cell in c.region.cells]
        self.assertEqual(len(hits), 1, f"cell {cell} owned {len(hits)} times")
        return hits[0]

    def test_shell_gets_building_material_partition_is_decided(self):
        regions, rooms = two_room_setup()
        plan = self.plan(regions, rooms, band=EconomicTierBand.RICH)
        self.assertFalse(plan.failures)
        self.assertEqual(self.material_at(plan.choices, (0, 0)), "brick")
        self.assertEqual(self.material_at(plan.choices, (6, 2)), "granite")
        for cell in ((6, 0), (6, 4)):  # partition ends are exterior per S0
            self.assertEqual(self.material_at(plan.choices, cell), "brick")

    def test_wealthy_default_picks_weakest(self):
        regions, rooms = two_room_setup()
        plan = self.plan(regions, rooms, band=EconomicTierBand.WEALTHY)
        self.assertEqual(self.material_at(plan.choices, (6, 2)), "wood")

    def test_explicit_policy_overrides_default(self):
        regions, rooms = two_room_setup()
        plan = self.plan(regions, rooms, band=EconomicTierBand.RICH,
                         policy=MaterialPolicy.MIN_STRENGTH)
        self.assertEqual(self.material_at(plan.choices, (6, 2)), "wood")

    def test_equal_strength_partition_goes_to_larger_room(self):
        a = room("a", x=0, y=0, width=7, depth=5)
        a.wall_material = "granite"                       # 35 cells
        b = room("b", x=6, y=0, width=9, depth=7)
        b.wall_material = "marble"                        # 63 cells, same 0.8
        regions = classify_wall_regions([a, b], 0, 3)
        plan = self.plan(regions, {a.uid_key: a, b.uid_key: b},
                         band=EconomicTierBand.RICH)
        self.assertEqual(self.material_at(plan.choices, (6, 2)), "marble")

    def test_shaft_side_partition_is_single_candidate_no_consumer(self):
        host = room("host", x=0, y=0, width=10, depth=10)
        host.wall_material = "granite"
        s = room("shaft", x=9, y=0, width=5, depth=5)
        s.is_shaft = True
        s.wall_material = "wood"
        regions = classify_wall_regions([host, s], 0, 2)
        rooms = {host.uid_key: host, s.uid_key: s}
        # Empty strength table would fail every consumer call — none happens.
        plan = self.plan(regions, rooms, strengths={})
        self.assertFalse(plan.failures)
        self.assertEqual(self.material_at(plan.choices, (9, 2)), "granite")

    def test_missing_strength_surfaces_failure_shell_still_decided(self):
        regions, rooms = two_room_setup()
        plan = self.plan(regions, rooms, band=EconomicTierBand.RICH,
                         strengths={"brick": 0.5})
        self.assertEqual(len(plan.failures), 1)
        failure = plan.failures[0]
        self.assertEqual(failure.failure, MaterialPolicyFailure.MISSING_STRENGTH)
        self.assertEqual(failure.region.provenance, WallProvenance.INTERIOR)
        self.assertIn((6, 2), failure.region.cells)
        self.assertEqual(self.material_at(plan.choices, (0, 0)), "brick")

    def test_input_room_order_does_not_change_selection(self):
        def signature(order):
            a = room("a", x=0, y=0, width=7, depth=5)
            a.wall_material = "wood"
            b = room("b", x=6, y=0, width=7, depth=5)
            b.wall_material = "granite"
            c = room("c", x=6, y=4, width=7, depth=6)
            c.wall_material = "marble"
            rooms = [a, b, c]
            placed = [rooms[i] for i in order]
            regions = classify_wall_regions(placed, 0, 3)
            plan = self.plan(regions, {r.uid_key: r for r in placed},
                             band=EconomicTierBand.RICH)
            return (sorted((tuple(sorted(ch.region.cells)), ch.system_material)
                           for ch in plan.choices),
                    tuple(f.reason for f in plan.failures))

        base = signature((0, 1, 2))
        self.assertEqual(base, signature((2, 1, 0)))
        self.assertEqual(base, signature((1, 2, 0)))
