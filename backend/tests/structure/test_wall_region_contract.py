"""S2: frozen typed contract for wall provenance and material policy IO."""
import unittest

from pydantic import ValidationError

from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.economy.materialPolicies import (
    BuildingEconomicContext, MaterialCandidate, MaterialPolicy,
    MaterialPolicyDecision, MaterialPolicyFailure, MaterialPolicyRequest,
)
from app.dataModel.locations.structure.wallRegion import WallProvenance, WallRegion


def candidate(key="room_0", material="stone", strength=0.8, area=35):
    return MaterialCandidate(
        system_material=material, structural_strength=strength,
        source_key=key, source_area=area)


def context(band=EconomicTierBand.MIDDLE):
    return BuildingEconomicContext(economic_tier="standard", band=band)


class WallRegionContractTests(unittest.TestCase):
    def test_region_is_frozen_typed_and_provenance_only(self):
        region = WallRegion(
            cells=frozenset({(6, 0), (6, 1)}), z_min=0, z_max=3,
            provenance=WallProvenance.INTERIOR, room_keys=("a_0", "b_0"))
        self.assertEqual(region.z_min, 0)
        self.assertEqual(region.z_max, 3)
        self.assertIsInstance(region.cells, frozenset)
        for field, value in (("cells", frozenset()), ("z_min", 5),
                             ("provenance", WallProvenance.EXTERIOR)):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                setattr(region, field, value)
        with self.assertRaises(ValidationError):
            WallRegion(cells=frozenset({(0, 0)}), z_min=0, z_max=1,
                       provenance=WallProvenance.INTERIOR, staircase_type="u")
        with self.assertRaises(ValidationError):
            WallRegion(cells=frozenset(), z_min=0, z_max=1,
                       provenance=WallProvenance.INTERIOR)

    def test_provenance_and_room_keys(self):
        self.assertEqual(set(WallProvenance),
                         {WallProvenance.EXTERIOR, WallProvenance.INTERIOR})
        region = WallRegion(
            cells=frozenset({(0, 0)}), z_min=0, z_max=0,
            provenance=WallProvenance.EXTERIOR)
        self.assertEqual(region.room_keys, ())
        # Candidate order is the caller's deterministic contract — the DTO
        # preserves it verbatim for the §11.3 first-candidate tie-break.
        ab = WallRegion(cells=frozenset({(0, 0)}), z_min=0, z_max=0,
                        provenance=WallProvenance.INTERIOR,
                        room_keys=("a_0", "b_0"))
        ba = WallRegion(cells=frozenset({(0, 0)}), z_min=0, z_max=0,
                        provenance=WallProvenance.INTERIOR,
                        room_keys=("b_0", "a_0"))
        self.assertNotEqual(ab.room_keys, ba.room_keys)


class MaterialPolicyContractTests(unittest.TestCase):
    def test_candidate_strength_bounds_and_nullable(self):
        self.assertIsNone(candidate(strength=None).structural_strength)
        for bad in (-0.1, 1.1):
            with self.subTest(strength=bad), self.assertRaises(ValidationError):
                candidate(strength=bad)
        with self.assertRaises(ValidationError):
            candidate(area=-1)

    def test_request_policy_is_optional_stub_context_required(self):
        request = MaterialPolicyRequest(candidates=(candidate(),),
                                        context=context())
        self.assertIsNone(request.policy)
        explicit = MaterialPolicyRequest(
            candidates=(candidate(),), context=context(),
            policy=MaterialPolicy.MAX_STRENGTH)
        self.assertEqual(explicit.policy, MaterialPolicy.MAX_STRENGTH)
        with self.assertRaises(ValidationError):
            MaterialPolicyRequest(candidates=(candidate(),))

    def test_context_carries_tier_and_band(self):
        ctx = context(EconomicTierBand.RICH)
        self.assertEqual(ctx.economic_tier, "standard")
        self.assertEqual(ctx.band, EconomicTierBand.RICH)
        with self.assertRaises(ValidationError):
            BuildingEconomicContext(band=EconomicTierBand.RICH)

    def test_first_policies_and_failure_vocabulary(self):
        self.assertEqual(set(MaterialPolicy),
                         {MaterialPolicy.MAX_STRENGTH,
                          MaterialPolicy.MIN_STRENGTH})
        self.assertEqual(set(MaterialPolicyFailure),
                         {MaterialPolicyFailure.NO_CANDIDATES,
                          MaterialPolicyFailure.MISSING_STRENGTH})

    def test_decision_exactly_one_outcome(self):
        won = MaterialPolicyDecision(candidate=candidate(),
                                     policy=MaterialPolicy.MIN_STRENGTH,
                                     reason="tie by area")
        self.assertIsNone(won.failure)
        lost = MaterialPolicyDecision(
            policy=MaterialPolicy.MIN_STRENGTH,
            failure=MaterialPolicyFailure.NO_CANDIDATES)
        self.assertIsNone(lost.candidate)
        for kwargs in (
                dict(policy=MaterialPolicy.MIN_STRENGTH),
                dict(candidate=candidate(), policy=MaterialPolicy.MIN_STRENGTH,
                     failure=MaterialPolicyFailure.NO_CANDIDATES)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                MaterialPolicyDecision(**kwargs)
