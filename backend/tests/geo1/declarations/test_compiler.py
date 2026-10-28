"""P2: declarations compile once; existing resolver executes both operation variants."""

from dataclasses import replace
from itertools import permutations
from typing import Annotated
from unittest import TestCase
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, StrictBool

from app.application.policy.declarations.compiler import compile_admission_policy, compile_value_policy
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as HydroMode
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.policy.declarations.fieldPolicy import EnabledFor, SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy, PolicyOwner, ValuePolicy
from app.dataModel.policy.declarations.policyIdentity import RuleKind, RuleIdentity, make_rule_id
from app.dataModel.policy.objectAdmissionPolicyDefinition import PlacementPolicyDefaults
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs, PolicySource, PolicySupportFact
from app.dataModel.policy.policyDecision import ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyIssueReason, PolicyState, PolicySupportState, RulePrecedence
from app.dataModel.policy.policyFacts import FactValue, KnownFact, UnknownFact, WaitingFact
from app.dataModel.policy.policyReferences import DirectValueRef
from app.dataModel.policy.policyRules import Equal, PolicyFallback, RequireSupportEffect, SelectBehaviorEffect
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.declarations.test_declarations import (
    Action, Reason, Owner, OtherOwner, Key, Settings, _POLICY, _FALSE, _TRUE, _PRIORITY, _TERMINAL,
)

CONFIG = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always", strict=True)


def sources(*instances):
    return PolicyInputs(models=tuple(PolicySource(type(obj), obj, (type(obj).__name__,)) for obj in instances))


def fixture(policy=_POLICY, value_type=StrictBool, cases=(_FALSE, _TRUE)):
    gate = EnabledFor(policy)
    selection = SelectByValue(policy, cases)
    class Root(BaseModel):
        model_config = CONFIG
        enabled: Annotated[StrictBool, gate] = True
    class Context(BaseModel):
        model_config = CONFIG
        flag: Annotated[value_type, selection]
    return Root, Context


def execute(spec, inputs, facts=None, mode=ResolutionMode.VALIDATE_ONLY, **kwargs):
    return PolicyResolver().resolve(spec, inputs, facts or PolicyFacts(), mode=mode, **kwargs)


class CompilerTests(TestCase):
    def test_field_cases_execute_on_existing_resolver_without_placement_priority(self):
        root, context = fixture()
        spec = compile_value_policy(_POLICY, (root, context))
        for enabled, flag, expected in ((False, True, Action.DISABLED),
                                        (True, False, Action.DECLARED), (True, True, Action.AUTO)):
            decision = execute(spec, sources(root(enabled=enabled), context(flag=flag)))
            self.assertEqual(decision.behavior, expected)
            self.assertIsNone(decision.effective_priority)
            self.assertEqual(decision.state, PolicyState.READY if enabled else PolicyState.DISABLED)
            restored = ValueSelectionDecision[Action, Reason].model_validate_json(decision.model_dump_json())
            self.assertEqual(restored, decision)

    def test_hydrology_and_independent_domain_use_same_compiler(self):
        class HydroOwner(PolicyOwner):
            pass
        policy = ValuePolicy[HydroMode, WaterPolicyReason](owner=HydroOwner,
            behavior_type=HydroMode, reason_type=WaterPolicyReason, disabled_behavior=HydroMode.DISABLED)
        cases = (ValueCase(when=False, behavior=HydroMode.DECLARED_ONLY), ValueCase(when=True, behavior=HydroMode.AUTORESOLVE))
        root, context = fixture(policy, cases=cases)
        spec = compile_value_policy(policy, (root, context))
        self.assertIs(execute(spec, sources(root(), context(flag=True))).require_behavior(), HydroMode.AUTORESOLVE)
        self.assertIs(execute(spec, sources(root(enabled=False))).require_behavior(), HydroMode.DISABLED)

    def test_compilation_does_not_construct_sources_or_execute_resolver(self):
        root, context = fixture()
        with patch.object(root, "__init__", side_effect=AssertionError("source constructed")), \
             patch.object(context, "__init__", side_effect=AssertionError("source constructed")), \
             patch.object(PolicyResolver, "resolve", side_effect=AssertionError("policy executed")):
            spec = compile_value_policy(_POLICY, (root, context))
        self.assertEqual(len(spec.rules), 3)

    def test_model_and_case_permutations_preserve_ids(self):
        root, context = fixture()
        expected = tuple(r.id for r in compile_value_policy(_POLICY, (root, context)).rules)
        for models in permutations((root, context)):
            self.assertEqual(tuple(r.id for r in compile_value_policy(_POLICY, models).rules), expected)
        forward, reverse = fixture(), fixture(cases=(_TRUE, _FALSE))
        self.assertEqual(tuple(r.id for r in compile_value_policy(_POLICY, forward).rules),
                         tuple(r.id for r in compile_value_policy(_POLICY, reverse).rules))

    def test_behavior_reason_and_precedence_changes_preserve_rule_identity(self):
        root, context = fixture()
        old = tuple(r.id for r in compile_value_policy(_POLICY, (root, context)).rules)
        changed = replace(_FALSE, behavior=Action.AUTO, reason=None, precedence=RulePrecedence(9))
        new_models = fixture(cases=(changed, _TRUE))
        new_spec = compile_value_policy(_POLICY, new_models)
        self.assertEqual(tuple(r.id for r in new_spec.rules), old)
        self.assertIs(execute(new_spec, sources(new_models[0](), new_models[1](flag=False))).behavior, Action.AUTO)

    def test_explicit_zero_precedence_overrides_descriptor_default(self):
        policy = replace(_POLICY, default_precedence=RulePrecedence(7))
        root, context = fixture(policy, cases=(replace(_FALSE, precedence=RulePrecedence(0)), _TRUE))
        rules = compile_value_policy(policy, (root, context)).rules
        cases = [r for r in rules if isinstance(r.effect, SelectBehaviorEffect)]
        by_value = {r.conditions[0].expected: r.precedence for r in cases}
        self.assertEqual(by_value, {False: 0, True: 7})

    def test_nullable_none_is_not_false_and_requires_explicit_case(self):
        root, context = fixture(value_type=StrictBool | None)
        spec = compile_value_policy(_POLICY, (root, context))
        for mode in ResolutionMode:
            result = execute(spec, sources(root(), context(flag=None)), mode=mode)
            self.assertIs(result.state, PolicyState.UNRESOLVED)
            self.assertEqual(result.issues[0].code, PolicyIssueReason.RULE_NO_MATCH)
        none_case = ValueCase(when=None, behavior=Action.DECLARED)
        root, context = fixture(value_type=StrictBool | None, cases=(_FALSE, _TRUE, none_case))
        result = execute(compile_value_policy(_POLICY, (root, context)), sources(root(), context(flag=None)))
        self.assertIs(result.behavior, Action.DECLARED)

    def test_unknown_waiting_and_runtime_fallback_are_preserved(self):
        policy = replace(_POLICY, fallback_rules=(PolicyFallback(PolicyIssueReason.UNKNOWN_FACT, Action.DISABLED, True),))
        root, context = fixture(policy, value_type=FactValue[bool])
        spec = compile_value_policy(policy, (root, context))
        issue = FieldPathError(("observed",), "missing observation")
        unknown = sources(root(), context(flag=UnknownFact(issue=issue)))
        self.assertIs(execute(spec, unknown).state, PolicyState.UNRESOLVED)
        runtime = execute(spec, unknown, mode=ResolutionMode.RUNTIME)
        self.assertIs(runtime.state, PolicyState.DISABLED)
        self.assertEqual(runtime.issues, (issue,))
        self.assertIs(runtime.behavior, Action.DISABLED)
        waiting = execute(spec, sources(root(), context(flag=WaitingFact(support_uids=("support",)))))
        self.assertIs(waiting.state, PolicyState.WAITING_SUPPORT)
        self.assertEqual(waiting.waiting_supports, ("support",))
        self.assertIs(execute(spec, sources(root(), context(flag=KnownFact(value=True)))).behavior, Action.AUTO)

    def test_multiple_gates_bind_their_own_models(self):
        root, context = fixture()
        class Category(BaseModel):
            model_config = CONFIG
            enabled: Annotated[StrictBool, EnabledFor(_POLICY)] = True
        spec = compile_value_policy(_POLICY, (root, context, Category))
        for root_enabled, category_enabled in ((False, True), (True, False), (False, False)):
            result = execute(spec, sources(root(enabled=root_enabled), Category(enabled=category_enabled)))
            self.assertIs(result.behavior, Action.DISABLED)
        result = execute(spec, sources(root(), Category(), context(flag=True)))
        self.assertIs(result.behavior, Action.AUTO)

    def test_wire_alias_metadata_is_discovered_and_strictness_preserved(self):
        class Aliases(BaseModel):
            model_config = CONFIG
            enabled: DefaultWhenMissing[Annotated[StrictBool, EnabledFor(_POLICY)]] = True
            flag: DefaultWhenMissing[Annotated[FactValue[bool], SelectByValue(_POLICY, (_FALSE, _TRUE))]]
        spec = compile_value_policy(_POLICY, (Aliases,))
        self.assertIs(execute(spec, sources(Aliases(flag=KnownFact(value=False)))).behavior, Action.DECLARED)
        with self.assertRaisesRegex(ValueError, "FactValue source requires FactValueRef"):
            DirectValueRef(FieldRef(lambda: Aliases, lambda source: source.flag))

    def test_unrelated_metadata_is_ignored_and_unrequested_models_are_not_discovered(self):
        unrelated = replace(_POLICY, owner=OtherOwner)
        class Mixed(BaseModel):
            model_config = CONFIG
            flag: Annotated[StrictBool, SelectByValue(_POLICY, (_FALSE, _TRUE)), EnabledFor(unrelated)]
        fixture()  # Loaded declarations outside the explicit tuple must not participate.
        spec = compile_value_policy(_POLICY, (Mixed,))
        self.assertEqual(len(spec.rules), 2)

    def test_conflicting_same_owner_descriptors_are_rejected(self):
        clone = replace(_POLICY)
        root, context = fixture(clone)
        with self.assertRaisesRegex(ValueError, "descriptors share owner"):
            compile_value_policy(_POLICY, (root, context))

    def test_invalid_gate_and_value_field_attachments_are_rejected(self):
        for annotation in (int, StrictBool | None, FactValue[bool]):
            class BadGate(BaseModel):
                model_config = CONFIG
                flag: Annotated[annotation, EnabledFor(_POLICY)]
            with self.subTest(annotation=annotation), self.assertRaises(ValueError):
                compile_value_policy(_POLICY, (BadGate,))
        for annotation in (int, str, object, list[bool], FactValue[int]):
            root, context = fixture(value_type=annotation)
            with self.subTest(annotation=annotation), self.assertRaises(ValueError):
                compile_value_policy(_POLICY, (root, context))
        class Coercible(BaseModel):
            model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
            enabled: Annotated[bool, EnabledFor(_POLICY)]
        with self.assertRaisesRegex(ValueError, "strict bool"):
            compile_value_policy(_POLICY, (Coercible,))

    def test_duplicate_fields_models_and_inherited_bindings_are_rejected(self):
        gate = EnabledFor(_POLICY)
        class Duplicate(BaseModel):
            model_config = CONFIG
            enabled: Annotated[StrictBool, gate, gate]
        with self.assertRaises(ValueError):
            compile_value_policy(_POLICY, (Duplicate,))
        root, context = fixture()
        class Child(root):
            pass
        self.assertEqual(len(compile_value_policy(_POLICY, (Child, context)).rules), 3)
        for models in ((root, root), (root, Child), [root, context], (root(),)):
            with self.assertRaises(ValueError):
                compile_value_policy(_POLICY, models)

    def test_compiler_operation_guards_and_model_contracts(self):
        with self.assertRaises(ValueError):
            compile_admission_policy(_POLICY, ())
        for config in (ConfigDict(extra="forbid", revalidate_instances="always"),
                       ConfigDict(frozen=True, extra="ignore", revalidate_instances="always"),
                       ConfigDict(frozen=True, extra="forbid")):
            class BadModel(BaseModel):
                model_config = config
                flag: Annotated[StrictBool, SelectByValue(_POLICY, (_FALSE, _TRUE))]
            with self.assertRaises(ValueError):
                compile_value_policy(_POLICY, (BadModel,))

    def test_compound_conflict_does_not_choose_lexical_id_winner(self):
        first = PolicyCaseDeclaration(key=Key.SELECT, conditions=(), effect=SelectBehaviorEffect(Action.AUTO))
        second = PolicyCaseDeclaration(key=Key.DISABLE, conditions=(), effect=SelectBehaviorEffect(Action.DECLARED))
        for cases in permutations((first, second)):
            policy = replace(_POLICY, cases=cases)
            result = execute(compile_value_policy(policy, ()), sources())
            self.assertIs(result.state, PolicyState.UNRESOLVED)
            self.assertEqual(result.issues[0].code, PolicyIssueReason.RULE_CONFLICT)
        policy = replace(_POLICY, cases=(first, replace(second, precedence=RulePrecedence(2))))
        self.assertIs(execute(compile_value_policy(policy, ()), sources()).behavior, Action.DECLARED)

    def test_compound_field_references_require_explicit_models(self):
        enabled = DirectValueRef(FieldRef(lambda: Settings, lambda s: s.enabled))
        case = PolicyCaseDeclaration(key=Key.SELECT, conditions=(Equal(enabled, True),),
                                     effect=SelectBehaviorEffect(Action.AUTO))
        policy = replace(_POLICY, cases=(case,))
        with self.assertRaisesRegex(ValueError, "explicit source"):
            compile_value_policy(policy, ())
        self.assertIs(execute(compile_value_policy(policy, (Settings,)), sources(Settings())).behavior, Action.AUTO)

    def test_admission_preserves_authored_zero_and_common_unknown_fallback(self):
        policy = AdmissionPolicy[Action, Reason](owner=Owner, behavior_type=Action, reason_type=Reason,
            authored_priority_ref=_PRIORITY, domain_priority_ref=_TERMINAL, terminal_priority_ref=_TERMINAL)
        root, context = fixture(policy)
        models = (root, context, Settings, PlacementPolicyDefaults)
        spec = compile_admission_policy(policy, models)
        self.assertIn(PolicyIssueReason.UNKNOWN_FACT, [f.reason for f in spec.fallback_rules])
        self.assertEqual(sum(r.id == make_rule_id(RuleIdentity(owner=Owner, kind=RuleKind.ZERO_PRIORITY)) for r in spec.rules), 1)
        for priority in (0, 3):
            result = execute(spec, sources(root(), context(flag=True), Settings(priority=priority), PlacementPolicyDefaults()))
            self.assertEqual(result.state, PolicyState.DISABLED if priority == 0 else PolicyState.READY)
            self.assertEqual(result.effective_priority, priority)
        with self.assertRaises(ValueError):
            compile_value_policy(policy, models)
        with self.assertRaises(ValueError):
            compile_admission_policy(policy, (root, context, Settings))

    def test_admission_support_resume_retains_original_provenance(self):
        case = PolicyCaseDeclaration(key=Key.SUPPORT, conditions=(), effect=RequireSupportEffect(("parent",)))
        policy = AdmissionPolicy[Action, Reason](owner=Owner, behavior_type=Action, reason_type=Reason,
            authored_priority_ref=_PRIORITY, domain_priority_ref=_TERMINAL, terminal_priority_ref=_TERMINAL, cases=(case,))
        root, context = fixture(policy)
        spec = compile_admission_policy(policy, (root, context, Settings, PlacementPolicyDefaults))
        inputs = sources(root(), context(flag=True), Settings(priority=3), PlacementPolicyDefaults())
        waiting = execute(spec, inputs, PolicyFacts(supports=(PolicySupportFact(uid="parent", state=PolicySupportState.PENDING),)))
        self.assertIs(waiting.state, PolicyState.WAITING_SUPPORT)
        resumed = execute(spec, inputs, PolicyFacts(supports=(PolicySupportFact(uid="parent", state=PolicySupportState.ACCEPTED),)), resume=waiting)
        self.assertIs(resumed.state, PolicyState.READY)
        self.assertTrue(all(p in resumed.provenance for p in waiting.provenance))

    def test_invalid_source_is_not_hidden_by_enabled_false(self):
        root, context = fixture()
        result = execute(compile_value_policy(_POLICY, (root, context)),
            sources(root(enabled=False), context(flag=True).model_copy(update={"flag": "true"})))
        self.assertIs(result.state, PolicyState.UNRESOLVED)
        self.assertEqual(result.issues[0].code, PolicyIssueReason.INVALID_INPUT)
