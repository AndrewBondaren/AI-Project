"""G2-G: real cascade sources feed one common policy executor before G10-A."""

from dataclasses import replace
from enum import StrEnum
from itertools import product
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.application.cascade.cascadeLink import Link
from app.application.cascade.contextResolver import extend
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, resolve_model
from app.application.policy.policyResolver import PolicyResolver
from app.application.policy.declarations.compiler import compile_value_policy
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import (
    BodyWaterGenerationSettings, CategoryWaterGenerationSettings, LakesGenerationFields,
    SeasGenerationFields, WorldHydrologyGenerationFields, WorldWaterGenerationSettings,
)
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterPolicyReason
from app.dataModel.hydrology.policy.hydrologyPolicyDefinition import (
    HYDROLOGY_GENERATION_POLICY, HYDROLOGY_AUTORESOLVE, HYDROLOGY_ENABLED, HydrologyGenerationPolicy,
)
from app.dataModel.cascade.cascadeGraph import BoundField
from app.dataModel.policy.declarations.fieldPolicy import SelectByValue
from app.dataModel.policy.declarations.policyIdentity import RuleIdentity, RuleKind, ValueBranch, make_rule_id
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyIssueReason, PolicyOperation, PolicyState
from app.dataModel.validation.enums.resolutionMode import ResolutionMode

_SPEC = compile_value_policy(HYDROLOGY_GENERATION_POLICY, (WorldHydrologyGenerationFields, WaterGenerationContext))


def context_for(root, category=None, body=None):
    context = extend(WaterGenerationContext.root(root), Link(Scope.WORLD, root.generation))
    context = extend(context, Link(Scope.CATEGORY, category or CategoryWaterGenerationSettings()))
    return extend(context, Link(Scope.WATER_BODY, body or BodyWaterGenerationSettings()))


def resolve(root, context, mode=ResolutionMode.VALIDATE_ONLY):
    return PolicyResolver().resolve(_SPEC, PolicyInputs(models=(
        PolicySource(WorldHydrologyGenerationFields, root, ("hydrology",)),
        PolicySource(WaterGenerationContext, context, ("resolved",)),
    )), PolicyFacts(), mode=mode)


class HydrologyGenerationTests(TestCase):
    def test_full_cascade_truth_table_and_root_hard_switch(self):
        for enabled, world, category, body in product((False, True), *((None, False, True),) * 3):
            root = WorldHydrologyGenerationFields(enabled=enabled, generation=WorldWaterGenerationSettings(autoresolve=world))
            context = context_for(root, CategoryWaterGenerationSettings(autoresolve=category),
                                  BodyWaterGenerationSettings(autoresolve=body))
            resolved = next((v for v in (body, category, world) if v is not None), False)
            expected = Mode.DISABLED if not enabled else Mode.AUTORESOLVE if resolved else Mode.DECLARED_ONLY
            for mode in ResolutionMode:
                with self.subTest(enabled=enabled, world=world, category=category, body=body, mode=mode):
                    decision = resolve(root, context, mode)
                    self.assertIs(decision.require_behavior(), expected)
                    self.assertIs(decision.state, PolicyState.READY if enabled else PolicyState.DISABLED)
                    self.assertIsNone(decision.effective_priority)
                    self.assertFalse(decision.issues)
                    self.assertTrue(decision.provenance)
                    self.assertIs(context.autoresolve, resolved)

    def test_missing_and_null_wire_are_inheritance_and_not_copies(self):
        for wire in ({}, {"generation": {}}, {"generation": {"autoresolve": None}}):
            root = resolve_model(WorldHydrologyGenerationFields, wire, ctx=ResolveContext(validate_only=True))
            context = context_for(root)
            result = resolve(root, context)
            self.assertIs(result.require_behavior(), Mode.DECLARED_ONLY)
            self.assertEqual(WorldHydrologyGenerationFields.model_validate_json(root.model_dump_json()), root)
            self.assertIsNone(root.generation.autoresolve)
            self.assertEqual(set(root.model_dump()), {"enabled", "generation"})
            self.assertNotIn("execution_mode", root.model_dump_json())

    def test_existing_category_owners_feed_the_same_graph(self):
        root = WorldHydrologyGenerationFields(generation=WorldWaterGenerationSettings(autoresolve=True))
        seas = SeasGenerationFields(sea_generation=CategoryWaterGenerationSettings(autoresolve=False),
                                    ocean_generation=CategoryWaterGenerationSettings(autoresolve=True))
        lakes = LakesGenerationFields(generation=CategoryWaterGenerationSettings(autoresolve=False))
        for source, expected in ((seas.sea_generation, Mode.DECLARED_ONLY),
                                 (seas.ocean_generation, Mode.AUTORESOLVE), (lakes.generation, Mode.DECLARED_ONLY)):
            context = context_for(root, source)
            self.assertIs(resolve(root, context).require_behavior(), expected)
            self.assertIs(resolve(root, context_for(root, source, BodyWaterGenerationSettings(autoresolve=True)))
                          .require_behavior(), Mode.AUTORESOLVE)
        self.assertIsNone(root.generation.water_fraction)

    def test_disabled_does_not_need_an_unbound_resolved_context(self):
        root = WorldHydrologyGenerationFields(enabled=False)
        result = PolicyResolver().resolve(_SPEC, PolicyInputs(models=(
            PolicySource(WorldHydrologyGenerationFields, root, ("hydrology",)),)), PolicyFacts(),
            mode=ResolutionMode.RUNTIME)
        self.assertIs(result.state, PolicyState.DISABLED)
        self.assertIs(result.require_behavior(), Mode.DISABLED)
        self.assertFalse(result.issues)
        self.assertEqual(result.reasons[0].common_reason, PolicyDisableReason.ENABLED_FALSE)
        self.assertEqual(result.provenance[0].rule_id, make_rule_id(RuleIdentity(
            owner=HydrologyGenerationPolicy, kind=RuleKind.ENABLED, field=BoundField(WorldHydrologyGenerationFields, "enabled"))))

    def test_unresolved_root_context_is_not_a_false_autoresolve(self):
        root = WorldHydrologyGenerationFields()
        for mode in ResolutionMode:
            decision = resolve(root, WaterGenerationContext.root(root), mode)
            self.assertIs(decision.state, PolicyState.UNRESOLVED)
            self.assertIsNone(decision.behavior)
            self.assertEqual(decision.issues[0].code, PolicyIssueReason.RULE_NO_MATCH)

    def test_strict_root_gate_and_unknown_enum_are_validation_errors(self):
        for invalid in (None, 0, 1, "false", "true", [], {}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                WorldHydrologyGenerationFields(enabled=invalid)
            with self.assertRaises(UnresolvedModelError):
                resolve_model(WorldHydrologyGenerationFields, {"enabled": invalid}, ctx=ResolveContext(validate_only=True))
        for wire in ({"generation": None}, {"generation": {"autoresolve": 1}},
                     {"generation": {"strategy": "unknown"}}, {"execution_mode": "autoresolve"}):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                WorldHydrologyGenerationFields.model_validate(wire)
        adapter = TypeAdapter(Mode)
        for value in (True, 1, "auto", "invalid"):
            with self.assertRaises(ValidationError):
                adapter.validate_python(value)

    def test_invalid_sources_are_not_hidden_by_disabled_or_runtime(self):
        root = WorldHydrologyGenerationFields(enabled=False)
        forged_context = context_for(root).model_copy(update={"autoresolve": "true"})
        forged_root = root.model_copy(update={"enabled": 0})
        for source, context in ((root, forged_context), (forged_root, context_for(root))):
            for mode in ResolutionMode:
                result = resolve(source, context, mode)
                self.assertIs(result.state, PolicyState.UNRESOLVED)
                self.assertIsNone(result.behavior)
                self.assertEqual(result.issues[0].code, PolicyIssueReason.INVALID_INPUT)

    def test_shared_enabled_binding_has_no_priority_or_local_domain_rules(self):
        spec = _SPEC
        self.assertIs(spec.operation, PolicyOperation.VALUE_SELECTION)
        self.assertFalse(hasattr(spec, "terminal_priority_ref"))
        self.assertEqual(len(spec.rules), 3)
        enabled_id = make_rule_id(RuleIdentity(owner=HydrologyGenerationPolicy, kind=RuleKind.ENABLED,
                                             field=BoundField(WorldHydrologyGenerationFields, "enabled")))
        self.assertEqual(sum(rule.id == enabled_id for rule in spec.rules), 1)
        class Foreign(StrEnum):
            DISABLED = "disabled"
        with self.assertRaises(ValueError):
            replace(spec, disabled_behavior=Foreign.DISABLED)
        self.assertIsNot(Mode, HydrologyScope)
        self.assertIsNot(Mode, Scope)

    def test_decision_roundtrip_preserves_typed_behavior_reason_and_provenance(self):
        for enabled, autoresolve in product((False, True), repeat=2):
            root = WorldHydrologyGenerationFields(enabled=enabled, generation=WorldWaterGenerationSettings(autoresolve=autoresolve))
            decision = resolve(root, context_for(root))
            restored = TypeAdapter(HydrologyGenerationDecision).validate_json(decision.model_dump_json())
            self.assertEqual(restored, decision)
            self.assertIsInstance(restored.require_behavior(), Mode)
            if enabled:
                self.assertIsInstance(restored.reasons[0].domain_reason, WaterPolicyReason)

    def test_policy_annotations_have_one_owner_and_original_field_identity(self):
        self.assertIn(HYDROLOGY_ENABLED, WorldHydrologyGenerationFields.model_fields["enabled"].metadata)
        self.assertIn(HYDROLOGY_AUTORESOLVE, WaterGenerationContext.model_fields["autoresolve"].metadata)
        self.assertIs(HYDROLOGY_AUTORESOLVE.policy, HYDROLOGY_GENERATION_POLICY)
        self.assertIs(HYDROLOGY_ENABLED.policy, HYDROLOGY_GENERATION_POLICY)
        for source in (WorldWaterGenerationSettings, CategoryWaterGenerationSettings, BodyWaterGenerationSettings):
            self.assertFalse(any(isinstance(meta, SelectByValue) for meta in source.model_fields["autoresolve"].metadata))
        expected_ids = {make_rule_id(RuleIdentity(owner=HydrologyGenerationPolicy, kind=RuleKind.ENABLED,
                                                field=BoundField(WorldHydrologyGenerationFields, "enabled")))}
        expected_ids.update(make_rule_id(RuleIdentity(owner=HydrologyGenerationPolicy, kind=RuleKind.VALUE_CASE,
            field=BoundField(WaterGenerationContext, "autoresolve"), branch=ValueBranch(case.when)))
            for case in HYDROLOGY_AUTORESOLVE.cases)
        self.assertEqual({r.id for r in _SPEC.rules}, expected_ids)

    def test_policy_metadata_does_not_change_wire_fields_or_restored_decision(self):
        root = WorldHydrologyGenerationFields(generation=WorldWaterGenerationSettings(autoresolve=True))
        context = context_for(root)
        restored_root = WorldHydrologyGenerationFields.model_validate_json(root.model_dump_json())
        restored_context = WaterGenerationContext.model_validate_json(context.model_dump_json())
        self.assertEqual(resolve(restored_root, restored_context), resolve(root, context))
        self.assertEqual(set(WorldHydrologyGenerationFields.model_json_schema()["properties"]), {"enabled", "generation"})
        self.assertNotIn("HYDROLOGY_GENERATION_POLICY", root.model_dump_json())

    def test_metadata_models_import_in_either_order_without_cycles(self):
        modules = ("app.dataModel.hydrology.policy.hydrologyPolicyDefinition",
                   "app.dataModel.hydrology.generation.waterGenerationSettings",
                   "app.dataModel.hydrology.generation.generationContext")
        for order in (modules, tuple(reversed(modules))):
            script = "import importlib; " + "; ".join(f"importlib.import_module({name!r})" for name in order)
            subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[3],
                           check=True, capture_output=True, text=True)
