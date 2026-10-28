"""Hydrology declarations run on the same compiler/resolver as unrelated domains."""

from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.policy.hydrologyPolicyFacts import collect_hydrology_policy_facts
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.placement.placementFields import WaterCategoryPlacementFields, WaterSourcePlacementFields
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    HydrologyPlacementBehaviorInputs, HydrologyPlacementGateInputs, HydrologyPolicySnapshot,
)
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredLakeSource
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyOrigin, PolicyState, PolicySupportState
from app.dataModel.policy.policyFacts import KnownFact, UnknownFact
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.placement_policy.fixtures import bind, coastline, execute, snapshot


class WaterPlacementPolicyTests(TestCase):
    def test_source_needs_no_support_or_future_water(self):
        binding = bind()
        self.assertFalse(binding.facts.supports)
        observed = binding.facts.models[0].instance
        self.assertIsNone(observed.target_has_water.value)
        self.assertEqual(execute(binding).state, PolicyState.READY)
        self.assertFalse(any(rule.effect.__class__.__name__ == "RequireSupportEffect" for rule in binding.spec.rules))

    def test_actual_category_default_remains_zero(self):
        result = execute(bind(category=HydrologySeasPolicy()))
        self.assertEqual(result.effective_priority, 0)
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertEqual(result.provenance[-1].origin, PolicyOrigin.DOMAIN_DEFAULT)

    def test_actual_category_values_change_decision(self):
        for priority in (0, 2, 7):
            with self.subTest(priority=priority):
                result = execute(bind(category=HydrologySeasPolicy(placement_specificity=priority)))
                self.assertEqual(result.effective_priority, priority)
                self.assertEqual(result.provenance[-2 if priority else -1].source_path,
                                 ("hydrology", "default_seas", "placement_specificity"))

    def test_authored_zero_does_not_inherit_category(self):
        result = execute(bind(coastline(priority=0)))
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertEqual(result.effective_priority, 0)
        self.assertEqual(result.provenance[-1].origin, PolicyOrigin.AUTHORED)

    def test_lake_has_same_authored_priority_owner(self):
        for priority, effective in ((None, 4), (0, 0), (2, 2)):
            result = execute(bind(AuthoredLakeSource(value=DeclaredLake(
                location_uid="lake", placement_specificity=priority)),
                category=HydrologyLakesPolicy(placement_specificity=4)))
            self.assertEqual(result.effective_priority, effective)

    def test_terminal_zero_is_selected_for_absent_category_priority(self):
        result = execute(bind(category=HydrologySeasPolicy(placement_specificity=None)))
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertEqual(result.provenance[-1].origin, PolicyOrigin.TERMINAL_DEFAULT)

    def test_gate_precedes_unknown_boundary_and_zero(self):
        for enabled, category_enabled in ((False, True), (True, False)):
            result = execute(bind(coastline(True), snapshot(mapping=False),
                                  enabled=enabled, category_enabled=category_enabled))
            self.assertEqual(result.state, PolicyState.DISABLED)
            self.assertEqual(result.reasons[0].common_reason, PolicyDisableReason.ENABLED_FALSE)
            self.assertFalse(result.issues)
            self.assertIsNone(result.effective_priority)

    def test_all_resolved_strategies_selected_by_metadata(self):
        for strategy in Strategy:
            self.assertEqual(execute(bind(strategy=strategy)).behavior, strategy)

    def test_wet_boundary_from_coarse_or_fine_cells(self):
        for fine in (False, True):
            result = execute(bind(coastline(True), snapshot(fine=fine)))
            self.assertEqual(result.state, PolicyState.READY)

    def test_authoritative_empty_mapping_is_dry(self):
        result = execute(bind(coastline(True), snapshot(mapped=())))
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertIn(WaterPolicyReason.DRY_TARGET, tuple(reason.domain_reason for reason in result.reasons))
        self.assertTrue(any(p.rule_id is not None for p in result.provenance))
        self.assertFalse(result.issues)

    def test_existing_body_without_liquid_cells_is_dry(self):
        result = execute(bind(coastline(True), snapshot(wet=False)))
        self.assertIn(WaterPolicyReason.DRY_TARGET, tuple(reason.domain_reason for reason in result.reasons))

    def test_accepted_missing_evidence_is_unknown(self):
        for evidence in (snapshot(mapped=None), snapshot(mapping=False), snapshot(hydro=False),
                         snapshot(mapped=("absent",))):
            facts = collect_hydrology_policy_facts(coastline(True), evidence)
            self.assertIsInstance(facts.target_has_water, UnknownFact)
            result = execute(bind(coastline(True), evidence))
            self.assertEqual(result.state, PolicyState.UNRESOLVED)
            self.assertTrue(result.issues)
            self.assertNotIn(WaterPolicyReason.DRY_TARGET, tuple(reason.domain_reason for reason in result.reasons))

    def test_equal_source_body_uid_and_legacy_aliases_do_not_replace_mapping(self):
        result = execute(bind(coastline(True), snapshot(bodies=("source",), mapped=None)))
        self.assertEqual(result.state, PolicyState.UNRESOLVED)

    def test_support_states_are_executed_by_common_engine(self):
        for support, expected in ((PolicySupportState.PENDING, PolicyState.WAITING_SUPPORT),
                                  (PolicySupportState.DISABLED, PolicyState.DISABLED),
                                  (PolicySupportState.MISSING, PolicyState.UNRESOLVED),
                                  (PolicySupportState.FAILED, PolicyState.UNRESOLVED),
                                  (PolicySupportState.CYCLE, PolicyState.UNRESOLVED),
                                  (None, PolicyState.UNRESOLVED)):
            with self.subTest(support=support):
                evidence = snapshot(support, mapping=False, hydro=False)
                facts = collect_hydrology_policy_facts(coastline(True), evidence)
                self.assertEqual(facts.target_has_water, KnownFact[bool | None](value=None))
                result = execute(bind(coastline(True), evidence))
                self.assertEqual(result.state, expected)
                if support is PolicySupportState.PENDING:
                    self.assertEqual(result.waiting_supports, ("source",))

    def test_boundary_zero_precedes_support_wait(self):
        result = execute(bind(coastline(True, priority=0), snapshot(PolicySupportState.PENDING)))
        self.assertEqual(result.state, PolicyState.DISABLED)
        self.assertFalse(result.waiting_supports)

    def test_multiple_physical_bodies_and_shared_body_are_supported(self):
        evidence = snapshot(bodies=("one", "two"), mapped=("one", "two"))
        self.assertEqual(execute(bind(coastline(True), evidence)).state, PolicyState.READY)
        mapping = SourceBodyMapping(entries=(
            SourceBodyMappingEntry(source_uid="other", body_uids=("physical",)),
            SourceBodyMappingEntry(source_uid="source", body_uids=("physical",))))
        evidence = HydrologyPolicySnapshot.model_validate(snapshot().model_copy(update={"source_mapping": mapping}))
        self.assertEqual(execute(bind(coastline(True), evidence)).state, PolicyState.READY)

    def test_rule_ids_do_not_depend_on_bound_target(self):
        first = bind(coastline(True), snapshot())
        second = bind(coastline(True, target="another"), snapshot(target="another"))
        self.assertEqual(tuple(rule.id for rule in first.spec.rules), tuple(rule.id for rule in second.spec.rules))

    def test_preview_runtime_known_results_agree(self):
        for evidence in (snapshot(), snapshot(mapped=()), snapshot(PolicySupportState.PENDING)):
            binding = bind(coastline(True), evidence)
            self.assertEqual(execute(binding), execute(binding, ResolutionMode.RUNTIME))

    def test_binding_does_not_execute_resolver(self):
        with patch.object(PolicyResolver, "resolve", side_effect=AssertionError("executed")):
            bind(coastline(True), snapshot())

    def test_snapshot_rejects_wrong_world_revision_and_orphan_mapping(self):
        evidence = snapshot()
        for update in ({"world_uid": "other"}, {"mapping_hydrology_ref": None}, {"hydrology": None},
                       {"mapping_hydrology_ref": evidence.mapping_hydrology_ref.model_copy(
                           update={"output_fingerprint": b"x" * 32})},
                       {"supports": evidence.supports * 2}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                HydrologyPolicySnapshot.model_validate(evidence.model_copy(update=update))

    def test_snapshot_round_trip(self):
        evidence = snapshot()
        self.assertEqual(HydrologyPolicySnapshot.model_validate_json(evidence.model_dump_json()), evidence)

    def test_mapping_is_sorted_unique_and_strict(self):
        for bodies in (("b", "a"), ("a", "a"), ["a"], (" ",)):
            with self.assertRaises(ValidationError):
                SourceBodyMappingEntry(source_uid="source", body_uids=bodies)
        entry = SourceBodyMappingEntry(source_uid="source", body_uids=())
        with self.assertRaises(ValidationError):
            SourceBodyMapping(entries=(entry, entry))

    def test_required_inputs_and_priority_reject_invalid_values(self):
        for owner in (WaterSourcePlacementFields, WaterCategoryPlacementFields):
            for invalid in (True, -1, "3", 1.0):
                with self.assertRaises(ValidationError):
                    owner(placement_specificity=invalid)
        for owner in (HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs, HydrologyPolicySnapshot):
            with self.assertRaises(ValidationError):
                owner.model_validate({})

    def test_no_raw_sources_or_wrong_category_owner(self):
        with self.assertRaises(ValueError):
            bind(source={"location_uid": "raw"})
        with self.assertRaises(ValueError):
            bind(category=HydrologyLakesPolicy(placement_specificity=3))

    def test_tampered_legacy_priority_is_not_coerced(self):
        source = coastline(True).model_copy(update={"placement_specificity": True})
        with self.assertRaises(ValidationError):
            bind(source)

    def test_tampered_actual_category_does_not_fall_back_to_projection_default(self):
        with self.assertRaises(ValidationError):
            bind(category=HydrologySeasPolicy().model_copy(update={"placement_specificity": "5"}))

    def test_unknown_runtime_uses_common_fallback_and_retains_issue(self):
        binding = bind(coastline(True), snapshot(mapped=None))
        preview = execute(binding)
        runtime = execute(binding, ResolutionMode.RUNTIME)
        self.assertEqual(preview.state, PolicyState.UNRESOLVED)
        self.assertEqual(runtime.state, PolicyState.DISABLED)
        self.assertEqual(runtime.issues, preview.issues)
        self.assertEqual(runtime.reasons[-1].common_reason, PolicyDisableReason.ERROR_FALLBACK)
        self.assertEqual(runtime.provenance[-1].origin, PolicyOrigin.FALLBACK)

    def test_snapshot_rejects_mutable_legacy_payload(self):
        evidence = snapshot()
        cell = evidence.hydrology.payload.coarse_hydro[0][1].model_copy(update={"liquid_candidate": []})
        payload = evidence.hydrology.payload.model_copy(update={"coarse_hydro": ((evidence.hydrology.payload.coarse_hydro[0][0], cell),)})
        envelope = evidence.hydrology.model_copy(update={"payload": payload})
        with self.assertRaises(ValidationError):
            HydrologyPolicySnapshot.model_validate(evidence.model_copy(update={"hydrology": envelope}))
